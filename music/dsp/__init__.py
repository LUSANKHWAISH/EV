"""Digital Signal Processing (DSP) foundation for EV audio playback."""
from .biquad import peaking_sos, sos_freq_response, apply_sos_filter
from .chain import EqualizerDSP, EQBand

__all__ = [
    "peaking_sos",
    "sos_freq_response",
    "apply_sos_filter",
    "EqualizerDSP",
    "EQBand",
]
