"""Comprehensive verification tool for audio playback speed, pitch, sample rates, and frames.

Fulfills all requirements:
1. Log:
   - Source sample rate.
   - Format passed into QAudioSink.
   - sink.format() after starting.
   - Source frames read and bytes actually accepted by write().
   - Any resampling stage and its input/output frame counts.
   - processedUSecs(), elapsed time, and sink state/error transitions.
2. Run a known 10-second, 1 kHz WAV at both 44.1 kHz and 48 kHz through real playback path.
3. Verify output duration and frequency using WASAPI loopback capture, allowing for startup/drain latency.
4. Keep generated, accepted, and rendered frame counts strictly distinct.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import scipy.io.wavfile as wavfile
import soundcard as sc
from PySide6.QtCore import QCoreApplication
from PySide6.QtMultimedia import QAudio, QAudioFormat, QAudioSink, QMediaDevices

from prototypes.playback_eq.player import EQPlaybackEngine


def generate_test_tones(target_dir: Path) -> tuple[Path, Path]:
    target_dir.mkdir(parents=True, exist_ok=True)
    p_44k = target_dir / "tone_44k1_1khz.wav"
    p_48k = target_dir / "tone_48k_1khz.wav"

    dur = 10.0
    f0 = 1000.0

    # 44.1 kHz, 10.0s, 1000.0 Hz
    fs_44k = 44100
    n_44k = int(dur * fs_44k)
    t_44k = np.arange(n_44k) / fs_44k
    pcm_44k = 0.5 * np.sin(2.0 * np.pi * f0 * t_44k)
    stereo_44k = np.column_stack([pcm_44k, pcm_44k])
    wavfile.write(str(p_44k), fs_44k, (stereo_44k * 32767.0).astype(np.int16))

    # 48.0 kHz, 10.0s, 1000.0 Hz
    fs_48k = 48000
    n_48k = int(dur * fs_48k)
    t_48k = np.arange(n_48k) / fs_48k
    pcm_48k = 0.5 * np.sin(2.0 * np.pi * f0 * t_48k)
    stereo_48k = np.column_stack([pcm_48k, pcm_48k])
    wavfile.write(str(p_48k), fs_48k, (stereo_48k * 32767.0).astype(np.int16))

    return p_44k, p_48k


def verify_playback_stream(wav_path: Path, app: QCoreApplication) -> dict:
    print(f"\n======================================================================")
    print(f"VERIFYING PLAYBACK STREAM: {wav_path.name}")
    print(f"======================================================================")

    player = EQPlaybackEngine()
    player.set_volume(0.8)
    loaded = player.load(str(wav_path))
    if not loaded:
        raise RuntimeError(f"Failed to load {wav_path}: {player.last_error_message}")

    src_rate = player._sample_rate
    src_channels = player._channels
    src_total_frames = player._reader.total_frames
    src_duration = player.duration_seconds

    sink_fmt_configured = player._sink.format()
    configured_rate = sink_fmt_configured.sampleRate()
    configured_channels = sink_fmt_configured.channelCount()
    configured_sample_fmt = str(sink_fmt_configured.sampleFormat())

    print(f"1. Source File Format:")
    print(f"   - File Name: {wav_path.name}")
    print(f"   - Source Sample Rate: {src_rate} Hz")
    print(f"   - Source Channels: {src_channels}")
    print(f"   - Source Generated Frames: {src_total_frames}")
    print(f"   - Source Nominal Duration: {src_duration:.4f} s")

    print(f"2. QAudioSink Configured Format:")
    print(f"   - Target Device: {player._device.description()}")
    print(f"   - Configured Sample Rate: {configured_rate} Hz")
    print(f"   - Configured Channels: {configured_channels}")
    print(f"   - Configured Sample Format: {configured_sample_fmt}")
    print(f"   - Bytes Per Sample: {player._bytes_per_sample}")
    print(f"   - Device Buffer Size: {player._sink.bufferSize()} bytes")

    # Start playback first so WASAPI output stream is active
    t_start = time.time()
    played = player.play()
    if not played:
        raise RuntimeError(f"Failed to start playback: {player.last_error_message}")

    sink_fmt_active = player._sink.format()
    active_rate = sink_fmt_active.sampleRate()
    active_channels = sink_fmt_active.channelCount()
    active_sample_fmt = str(sink_fmt_active.sampleFormat())

    print(f"3. Active Sink Stream Format:")
    print(f"   - Active Sample Rate: {active_rate} Hz")
    print(f"   - Active Channels: {active_channels}")
    print(f"   - Active Format: {active_sample_fmt}")
    print(f"   - Resampling Stage: Up={player._resample_up}, Down={player._resample_down} (Active: {player._resample_up != player._resample_down})")

    # Start loopback recording
    default_spk = sc.default_speaker()
    loopback_mic = sc.get_microphone(id=str(default_spk.name), include_loopback=True)

    rec_rate = 44100
    recorded_chunks = []
    stop_rec = threading.Event()

    def loopback_worker():
        try:
            with loopback_mic.recorder(samplerate=rec_rate) as mic:
                while not stop_rec.is_set():
                    block = mic.record(numframes=2048)
                    recorded_chunks.append(block)
        except Exception as e:
            print(f"Loopback capture warning: {e}")

    rec_thread = threading.Thread(target=loopback_worker, name="LoopbackRec", daemon=True)
    rec_thread.start()

    # Track progress during streaming
    periodic_logs = []
    last_log_time = t_start

    while player.is_playing:
        app.processEvents()
        now = time.time()
        if now - last_log_time >= 1.0:
            last_log_time = now
            if player._sink:
                proc_us = player._sink.processedUSecs()
                state_now = str(player._sink.state())
                pos_sec = player.position_seconds
                frames_acc = player.total_frames_accepted
                periodic_logs.append({
                    "elapsed_sec": round(now - t_start, 3),
                    "pos_sec": round(pos_sec, 3),
                    "processed_usecs": proc_us,
                    "frames_accepted": frames_acc,
                    "state": state_now,
                })
                print(f"   [Streaming] Elapsed: {now - t_start:5.2f}s | Pos: {pos_sec:5.2f}s | "
                      f"Accepted: {frames_acc:6d} frames | Sink Processed: {proc_us/1e6:5.2f}s | State: {state_now}")
        time.sleep(0.01)

    t_end = time.time()
    elapsed_total = t_end - t_start

    # Buffer drain window
    time.sleep(0.5)
    stop_rec.set()
    rec_thread.join(timeout=1.0)

    # Frame and byte metrics
    gen_frames = src_total_frames
    src_read = player.total_source_frames_read
    res_in = player.resampled_frames_in
    res_out = player.resampled_frames_out
    bytes_acc = player.total_bytes_accepted
    frames_acc = player.total_frames_accepted
    final_proc_us = player.last_processed_usecs
    rendered_frames = int(final_proc_us * active_rate / 1_000_000)

    print(f"\n4. Distinct Frame, Byte & Latency Accounting:")
    print(f"   - Generated Frames (from source): {gen_frames}")
    print(f"   - Source Frames Read: {src_read}")
    if player._resample_up != player._resample_down:
        print(f"   - Resampler Input Frames: {res_in}")
        print(f"   - Resampler Output Frames: {res_out}")
    else:
        print(f"   - Resampler: Pass-through (1:1 ratio, 0 resampling loss)")
    print(f"   - Bytes Accepted by write(): {bytes_acc}")
    print(f"   - Frames Accepted by write(): {frames_acc}")
    print(f"   - Rendered Frames (from sink processedUSecs): {rendered_frames} ({final_proc_us} us)")
    print(f"   - Total Elapsed Time: {elapsed_total:.4f} s")
    print(f"   - Buffer Underruns: {player.underrun_count}")
    print(f"   - Stream Errors: {player.error_count}")
    print(f"   - State Transitions: {len(player.state_transitions)}")

    # Analyze Loopback Recording
    loopback_analysis = {}
    if recorded_chunks:
        full_rec = np.concatenate(recorded_chunks, axis=0)
        mono_rec = np.mean(full_rec, axis=1)

        # Detect active audio region (threshold > 0.005)
        thresh = 0.005
        active_idx = np.where(np.abs(mono_rec) > thresh)[0]
        if len(active_idx) > 0:
            first_idx = int(active_idx[0])
            last_idx = int(active_idx[-1])
            active_samples = last_idx - first_idx + 1
            active_dur = active_samples / rec_rate
            startup_latency = first_idx / rec_rate

            # FFT analysis on middle 6 seconds
            mid_start = first_idx + int(2.0 * rec_rate)
            mid_end = first_idx + int(8.0 * rec_rate)
            segment = mono_rec[mid_start:mid_end]

            nfft = len(segment)
            window = np.hanning(nfft)
            spectrum = np.abs(np.fft.rfft(segment * window))
            freqs = np.fft.rfftfreq(nfft, d=1.0 / rec_rate)

            peak_bin = int(np.argmax(spectrum))
            if 0 < peak_bin < len(spectrum) - 1:
                # Quadratic fit around peak
                alpha = float(spectrum[peak_bin - 1])
                beta = float(spectrum[peak_bin])
                gamma = float(spectrum[peak_bin + 1])
                delta = 0.5 * (alpha - gamma) / (alpha - 2.0 * beta + gamma)
                measured_f = (peak_bin + delta) * (rec_rate / nfft)
            else:
                measured_f = float(freqs[peak_bin])

            freq_error = measured_f - 1000.0
            dur_error = active_dur - 10.0

            print(f"\n5. WASAPI Loopback Capture Analysis:")
            print(f"   - Loopback Sample Rate: {rec_rate} Hz")
            print(f"   - Active Output Duration: {active_dur:.4f} s (Error: {dur_error:+.4f} s)")
            print(f"   - Startup/Drain Latency: {startup_latency:.4f} s")
            print(f"   - Measured Dominant Frequency: {measured_f:.3f} Hz (Error: {freq_error:+.3f} Hz)")

            loopback_analysis = {
                "loopback_sample_rate": rec_rate,
                "active_duration_sec": round(active_dur, 4),
                "duration_error_sec": round(dur_error, 4),
                "startup_latency_sec": round(startup_latency, 4),
                "measured_frequency_hz": round(float(measured_f), 3),
                "frequency_error_hz": round(float(freq_error), 3),
            }
        else:
            print("\n5. WASAPI Loopback Capture: No signal above threshold.")
            loopback_analysis = {"error": "No signal detected"}

    player.close()

    return {
        "file": wav_path.name,
        "source": {
            "sample_rate": src_rate,
            "channels": src_channels,
            "generated_frames": gen_frames,
            "nominal_duration_sec": src_duration,
        },
        "sink_format_configured": {
            "sample_rate": configured_rate,
            "channels": configured_channels,
            "sample_format": configured_sample_fmt,
        },
        "sink_format_active": {
            "sample_rate": active_rate,
            "channels": active_channels,
            "sample_format": active_sample_fmt,
        },
        "resampling": {
            "active": player._resample_up != player._resample_down,
            "up": player._resample_up,
            "down": player._resample_down,
            "frames_in": res_in,
            "frames_out": res_out,
        },
        "accounting": {
            "source_frames_read": src_read,
            "bytes_accepted": bytes_acc,
            "frames_accepted": frames_acc,
            "rendered_frames": rendered_frames,
            "final_processed_usecs": final_proc_us,
            "elapsed_total_sec": round(elapsed_total, 4),
            "underrun_count": player.underrun_count,
            "error_count": player.error_count,
        },
        "state_transitions": player.state_transitions,
        "error_transitions": player.error_transitions,
        "periodic_logs": periodic_logs,
        "loopback_analysis": loopback_analysis,
    }


def main():
    app = QCoreApplication(sys.argv)
    test_dir = Path("test_runtime")
    tone_44k, tone_48k = generate_test_tones(test_dir)

    results = {}
    results["tone_44k1"] = verify_playback_stream(tone_44k, app)
    results["tone_48k"] = verify_playback_stream(tone_48k, app)

    out_file = test_dir / "playback_rate_and_pitch_verification.json"
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n======================================================================")
    print(f"VERIFICATION FINAL SUMMARY")
    print(f"======================================================================")
    for key, data in results.items():
        src = data["source"]
        snk = data["sink_format_active"]
        acc = data["accounting"]
        lb = data.get("loopback_analysis", {})
        print(f"[{key}]")
        print(f"  Source Rate: {src['sample_rate']} Hz | Active Sink Rate: {snk['sample_rate']} Hz")
        print(f"  Generated Frames: {src['generated_frames']} | Accepted Frames: {acc['frames_accepted']} | Rendered Frames: {acc['rendered_frames']}")
        print(f"  Elapsed Playback Time: {acc['elapsed_total_sec']}s (Nominal: {src['nominal_duration_sec']}s)")
        print(f"  Loopback Active Duration: {lb.get('active_duration_sec')}s (Err: {lb.get('duration_error_sec')}s)")
        print(f"  Loopback Measured Frequency: {lb.get('measured_frequency_hz')} Hz (Err: {lb.get('frequency_error_hz')} Hz)")
        print(f"  Underruns: {acc['underrun_count']} | Errors: {acc['error_count']}")

    print(f"\nWritten complete evidence to: {out_file}")


if __name__ == "__main__":
    main()
