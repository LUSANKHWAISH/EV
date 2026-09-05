"""
Production openWakeWord Wake-Word Detection Adapter for E.V. (Task 014F-1).

Integrates the openWakeWord engine as a concrete EVWakeWordProvider adapter.
Processes canonical 16 kHz mono 16-bit PCM AudioFrames, accumulates samples via
AudioFrameRechunker (480 -> 1280 samples / 80 ms), and evaluates wake-phrase
activation against a configurable detection threshold.

Security & Architecture Invariants:
  1. Implements the public EVWakeWordProvider boundary from core.voice_wakeword.
  2. Pure detection trigger only: zero execution authority, zero orchestrator calls,
     zero agent/task execution, zero GOD MODE.
  3. Raw audio is memory-only: zero disk writes, zero WAV files, zero telemetry.
  4. Local offline inference only: zero cloud/network streaming during processing.
  5. Deterministic sample accumulation and exact PCM sample preservation.
  6. Thread-safe execution under multi-threaded voice runtimes.
"""
from __future__ import annotations

import logging
import os
import threading
from typing import Any, Dict, List, Optional, Sequence, Union

import numpy as np

from core.voice_capture import (
    DEFAULT_CHANNELS,
    DEFAULT_SAMPLE_RATE,
    DEFAULT_SAMPLE_WIDTH,
    AudioFormatError,
    AudioFrame,
)
from core.voice_wakeword import (
    DEFAULT_RECHUNKER_TARGET_SAMPLES,
    DEFAULT_TARGET_WAKE_PHRASE,
    AudioFrameRechunker,
    EVWakeWordProvider,
    WakeWordResult,
)

logger = logging.getLogger("ev.voice.wakeword.openwakeword")

DEFAULT_WAKEWORD_MODEL_DIR: str = r"D:\EV\models\wakeword"
DEFAULT_DETECTION_THRESHOLD: float = 0.50
DEFAULT_INFERENCE_FRAMEWORK: str = "onnx"
DEFAULT_STAGE1_CANDIDATE_MODEL: str = r"D:\EV\models\wakeword\candidates\hey_ev_human_v2.onnx"
DEFAULT_PRODUCTION_BASELINE_MODEL: str = r"D:\EV\models\wakeword\hey_ev.onnx"


class OpenWakeWordProvider(EVWakeWordProvider):
    """
    Production wake-word detection provider using openWakeWord.

    Accepts canonical 30 ms (480 samples @ 16 kHz) AudioFrames, rechunks them
    losslessly into 80 ms (1280 samples) evaluation windows, and runs local
    CPU inference.
    """

    def __init__(
        self,
        wakeword_models: Optional[Sequence[str]] = None,
        model_dir: Optional[str] = None,
        target_phrase: str = DEFAULT_TARGET_WAKE_PHRASE,
        threshold: float = DEFAULT_DETECTION_THRESHOLD,
        inference_framework: str = DEFAULT_INFERENCE_FRAMEWORK,
        model_instance: Optional[Any] = None,
        enable_speex_noise_suppression: bool = False,
        vad_threshold: float = 0.0,
        custom_verifier_models: Optional[Dict[str, Any]] = None,
        custom_verifier_threshold: float = 0.1,
    ) -> None:
        """
        Initialize the OpenWakeWordProvider.

        Args:
            wakeword_models: List of model names or filepaths to load.
            model_dir: Directory containing wake word models.
            target_phrase: Target wake phrase name (for reporting / results).
            threshold: Activation threshold in range [0.0, 1.0].
            inference_framework: "tflite" or "onnx".
            model_instance: Optional injected model instance for testing/DI.
            enable_speex_noise_suppression: Speex noise suppression flag.
            vad_threshold: Silero VAD filtering threshold (0 disables).
            custom_verifier_models: Optional verifier models dict.
            custom_verifier_threshold: Verification threshold.
        """
        # Validate threshold
        if not isinstance(threshold, (int, float)):
            raise TypeError(f"threshold must be numeric, got {type(threshold).__name__}")
        if not (0.0 <= float(threshold) <= 1.0):
            raise ValueError(f"threshold must be in range [0.0, 1.0], got {threshold}")
        self._threshold: float = float(threshold)

        # Validate target phrase
        if not isinstance(target_phrase, str) or not target_phrase.strip():
            raise ValueError("target_phrase must be a non-empty string")
        self._target_phrase: str = target_phrase.strip()

        # Model configuration
        self._model_dir: str = (
            model_dir
            or os.getenv("EV_WAKEWORD_MODEL_DIR")
            or DEFAULT_WAKEWORD_MODEL_DIR
        )
        self._wakeword_models: List[str] = list(wakeword_models) if wakeword_models is not None else []
        self._inference_framework: str = inference_framework
        self._enable_speex: bool = enable_speex_noise_suppression
        self._vad_threshold: float = vad_threshold
        self._custom_verifier_models: Dict[str, Any] = custom_verifier_models or {}
        self._custom_verifier_threshold: float = custom_verifier_threshold

        # Frame rechunker: 480 -> 1280 samples @ 16 kHz mono signed PCM16
        self._rechunker: AudioFrameRechunker = AudioFrameRechunker(
            target_samples=DEFAULT_RECHUNKER_TARGET_SAMPLES,
            sample_rate=DEFAULT_SAMPLE_RATE,
            channels=DEFAULT_CHANNELS,
            sample_width=DEFAULT_SAMPLE_WIDTH,
        )

        # Internal state & synchronization
        self._lock = threading.Lock()
        self._model: Optional[Any] = model_instance
        self._processed_frames_count: int = 0
        self._is_initialized: bool = model_instance is not None

        # Eagerly initialize if model_instance was not injected
        if self._model is None:
            self._initialize_model()

    def _initialize_model(self) -> None:
        """
        Load openWakeWord model backend with clear error reporting.
        """
        try:
            import openwakeword
            from openwakeword.model import Model
        except ImportError as exc:
            raise RuntimeError(
                "openwakeword is not installed in the environment. "
                "Install via 'pip install openwakeword'."
            ) from exc

        try:
            # Build models list: resolve model names / paths against model_dir if necessary
            models_to_load: List[str] = []
            raw_models = list(self._wakeword_models)
            if not raw_models:
                if os.path.exists(DEFAULT_STAGE1_CANDIDATE_MODEL):
                    raw_models.append(DEFAULT_STAGE1_CANDIDATE_MODEL)
                elif os.path.exists(DEFAULT_PRODUCTION_BASELINE_MODEL):
                    raw_models.append(DEFAULT_PRODUCTION_BASELINE_MODEL)

            for mdl in raw_models:
                if os.path.isabs(mdl) or os.path.exists(mdl):
                    models_to_load.append(mdl)
                else:
                    candidate = os.path.join(self._model_dir, mdl)
                    if os.path.exists(candidate):
                        models_to_load.append(candidate)
                    else:
                        models_to_load.append(mdl)

            self._model = Model(
                wakeword_models=models_to_load,
                enable_speex_noise_suppression=self._enable_speex,
                vad_threshold=self._vad_threshold,
                custom_verifier_models=self._custom_verifier_models,
                custom_verifier_threshold=self._custom_verifier_threshold,
                inference_framework=self._inference_framework,
            )
            self._is_initialized = True
            logger.info(
                "OpenWakeWordProvider initialized successfully (models=%s, framework=%s)",
                list(self._model.models.keys()) if hasattr(self._model, "models") else self._wakeword_models,
                self._inference_framework,
            )
        except Exception as exc:
            self._is_initialized = False
            self._model = None
            raise RuntimeError(
                f"Failed to initialize openWakeWord model: {exc}"
            ) from exc

    # ------------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------------
    @property
    def provider_name(self) -> str:
        """Human-readable provider identifier."""
        return "openwakeword"

    @property
    def target_phrase(self) -> str:
        """Configured target wake phrase identifier."""
        return self._target_phrase

    @property
    def threshold(self) -> float:
        """Configured detection confidence threshold [0.0, 1.0]."""
        return self._threshold

    @property
    def is_available(self) -> bool:
        """Return True if openWakeWord provider is initialized and ready."""
        with self._lock:
            return self._is_initialized and self._model is not None

    @property
    def loaded_models(self) -> List[str]:
        """Return list of loaded model names."""
        with self._lock:
            if self._model is not None and hasattr(self._model, "models"):
                return list(self._model.models.keys())
            return list(self._wakeword_models)

    @property
    def processed_frames_count(self) -> int:
        """Total number of canonical AudioFrames ingested."""
        with self._lock:
            return self._processed_frames_count

    # ------------------------------------------------------------------------
    # Detection Engine
    # ------------------------------------------------------------------------
    def process_frame(self, frame: AudioFrame) -> Optional[WakeWordResult]:
        """
        Process a canonical AudioFrame through the openWakeWord detection engine.

        Performs:
          1. Validation of AudioFrame format (16 kHz mono 16-bit PCM).
          2. Rechunking into 1280-sample (80 ms) windows via AudioFrameRechunker.
          3. Lossless conversion from raw PCM bytes to int16 NumPy array.
          4. openWakeWord model prediction.
          5. Threshold evaluation and immutable WakeWordResult generation.

        Returns:
          WakeWordResult if evaluated and wake phrase detected, or None.
        """
        if not isinstance(frame, AudioFrame):
            raise TypeError(f"Expected AudioFrame, got {type(frame).__name__}")

        if (
            frame.sample_rate != DEFAULT_SAMPLE_RATE
            or frame.channels != DEFAULT_CHANNELS
            or frame.sample_width != DEFAULT_SAMPLE_WIDTH
        ):
            raise AudioFormatError(
                f"AudioFrame format mismatch: expected rate={DEFAULT_SAMPLE_RATE}, "
                f"channels={DEFAULT_CHANNELS}, width={DEFAULT_SAMPLE_WIDTH}; "
                f"got rate={frame.sample_rate}, channels={frame.channels}, width={frame.sample_width}"
            )

        with self._lock:
            if not self._is_initialized or self._model is None:
                raise RuntimeError("OpenWakeWordProvider is not initialized")

            self._processed_frames_count += 1

            # Push into 480 -> 1280 rechunker
            rechunked_frames = self._rechunker.push_frame(frame)
            if not rechunked_frames:
                return None

            # Process each accumulated 1280-sample window
            highest_result: Optional[WakeWordResult] = None

            for chunk in rechunked_frames:
                # Lossless PCM16 conversion to NumPy 1D array of int16
                audio_array = np.frombuffer(chunk.data, dtype=np.int16)

                # Execute openWakeWord model prediction
                try:
                    predictions: Dict[str, float] = self._model.predict(audio_array)
                except Exception as exc:
                    logger.error("openWakeWord prediction error: %s", exc)
                    raise RuntimeError(f"openWakeWord prediction failure: {exc}") from exc

                if not isinstance(predictions, dict):
                    logger.warning("Unexpected prediction return type: %s", type(predictions))
                    continue

                # Check predictions against threshold
                for model_name, score in predictions.items():
                    score_val = float(score)
                    if score_val >= self._threshold:
                        res = WakeWordResult(
                            detected=True,
                            keyword=model_name,
                            confidence=min(1.0, max(0.0, score_val)),
                            timestamp=chunk.timestamp,
                        )
                        if highest_result is None or res.confidence > highest_result.confidence:
                            highest_result = res

            return highest_result

    # ------------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------------
    def reset(self) -> None:
        """
        Reset rechunker buffer, internal model prediction buffers, and history.
        Ensures zero stale wake detections survive across cycles.
        """
        with self._lock:
            self._rechunker.reset()
            if self._model is not None and hasattr(self._model, "reset"):
                try:
                    self._model.reset()
                except Exception as exc:
                    logger.debug("Error resetting openWakeWord model: %s", exc)
            self._processed_frames_count = 0

    def close(self) -> None:
        """Release resources and clear state. Idempotent."""
        self.reset()
