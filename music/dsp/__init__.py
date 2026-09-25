"""Digital Signal Processing (DSP) foundation for EV audio playback."""
from .biquad import peaking_sos, sos_freq_response, apply_sos_filter
from .chain import EqualizerDSP, EQBand, EQ_10_BAND_FREQUENCIES, EQ_DEFAULT_Q
from .store import EQStore, validate_eq_data, DEFAULT_EQ_DATA

__all__ = [
    "peaking_sos",
    "sos_freq_response",
    "apply_sos_filter",
    "EqualizerDSP",
    "EQBand",
    "EQ_10_BAND_FREQUENCIES",
    "EQ_DEFAULT_Q",
    "EQStore",
    "validate_eq_data",
    "DEFAULT_EQ_DATA",
]
