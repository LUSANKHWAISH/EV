"""
Task 014B: Audio Capture Abstraction & Ring Buffer test suite.

Verifies:
  A. AudioFrame construction, validation, duration calculation, and privacy.
  B. AudioRingBuffer FIFO ordering, capacity, oldest-frame eviction, peek/read_many.
  C. Thread-safe concurrency for writers and reader/writer pairs.
  D. MockAudioCaptureProvider lifecycle, frame injection, and silence generation.
  E. Privacy invariants (zero disk persistence, no raw audio byte dumps).
"""
import os
import threading
import time
from typing import List

import pytest

from core.voice_capture import (
    DEFAULT_BYTES_PER_FRAME,
    DEFAULT_CHANNELS,
    DEFAULT_FRAME_DURATION_MS,
    DEFAULT_SAMPLE_RATE,
    DEFAULT_SAMPLE_WIDTH,
    AudioCaptureError,
    AudioFormatError,
    AudioFrame,
    AudioRingBuffer,
    BufferClosedError,
    EVAudioCaptureProvider,
    MockAudioCaptureProvider,
    create_silence_frame,
)


# ============================================================================
# A. AudioFrame Tests
# ============================================================================
class TestAudioFrame:
    """Tests for AudioFrame immutability, validation, and contract."""

    def test_valid_default_construction(self):
        data = b"\x00" * DEFAULT_BYTES_PER_FRAME
        frame = AudioFrame(data=data)
        assert frame.data == data
        assert frame.sample_rate == DEFAULT_SAMPLE_RATE
        assert frame.channels == DEFAULT_CHANNELS
        assert frame.sample_width == DEFAULT_SAMPLE_WIDTH
        assert frame.sample_count == 480
        assert frame.duration_ms == pytest.approx(30.0, rel=1e-3)
        assert frame.duration_seconds == pytest.approx(0.030, rel=1e-3)
        assert frame.is_canonical() is True

    def test_valid_custom_construction(self):
        # 8000 Hz, 2 channels, 16-bit (4 bytes per sample block), 160 samples = 640 bytes
        data = b"\x01\x02\x03\x04" * 160
        frame = AudioFrame(data=data, sample_rate=8000, channels=2, sample_width=2)
        assert frame.sample_rate == 8000
        assert frame.channels == 2
        assert frame.sample_width == 2
        assert frame.sample_count == 160
        assert frame.duration_seconds == pytest.approx(0.020, rel=1e-3)
        assert frame.is_canonical() is False

    def test_bytearray_input_converted_to_immutable_bytes(self):
        mutable_data = bytearray(b"\xaa\xbb" * 100)
        frame = AudioFrame(data=mutable_data)
        assert isinstance(frame.data, bytes)
        assert frame.data == bytes(mutable_data)

    def test_empty_data_rejected(self):
        with pytest.raises(AudioFormatError, match="cannot be empty"):
            AudioFrame(data=b"")

    def test_non_bytes_rejected(self):
        with pytest.raises(AudioFormatError, match="must be bytes-like"):
            AudioFrame(data="not_bytes")  # type: ignore[arg-type]

        with pytest.raises(AudioFormatError, match="must be bytes-like"):
            AudioFrame(data=12345)  # type: ignore[arg-type]

        with pytest.raises(AudioFormatError, match="must be bytes-like"):
            AudioFrame(data=None)  # type: ignore[arg-type]

    def test_invalid_sample_rate_rejected(self):
        data = b"\x00\x00" * 100
        with pytest.raises(AudioFormatError, match="sample_rate must be > 0"):
            AudioFrame(data=data, sample_rate=0)

        with pytest.raises(AudioFormatError, match="sample_rate must be > 0"):
            AudioFrame(data=data, sample_rate=-16000)

    def test_invalid_channels_rejected(self):
        data = b"\x00\x00" * 100
        with pytest.raises(AudioFormatError, match="channels must be > 0"):
            AudioFrame(data=data, channels=0)

        with pytest.raises(AudioFormatError, match="channels must be > 0"):
            AudioFrame(data=data, channels=-1)

    def test_invalid_sample_width_rejected(self):
        data = b"\x00\x00" * 100
        with pytest.raises(AudioFormatError, match="sample_width must be > 0"):
            AudioFrame(data=data, sample_width=0)

        with pytest.raises(AudioFormatError, match="sample_width must be > 0"):
            AudioFrame(data=data, sample_width=-2)

    def test_unaligned_data_length_rejected(self):
        # 1 ch, 2 bytes sample_width -> must be even number of bytes
        with pytest.raises(AudioFormatError, match="not an integral multiple"):
            AudioFrame(data=b"\x01\x02\x03", sample_rate=16000, channels=1, sample_width=2)

        # 2 ch, 2 bytes sample_width -> must be multiple of 4 bytes
        with pytest.raises(AudioFormatError, match="not an integral multiple"):
            AudioFrame(data=b"\x01\x02\x03\x04\x05\x06", sample_rate=16000, channels=2, sample_width=2)

    def test_frozen_immutability(self):
        frame = AudioFrame(data=b"\x00\x00" * 50)
        with pytest.raises((AttributeError, TypeError)):
            frame.sample_rate = 8000  # type: ignore[misc]

    def test_repr_does_not_expose_raw_bytes(self):
        sensitive_payload = b"SECRET_VOICE_PAYLOAD_ABCXYZ" * 20
        # Pad to multiple of 2
        if len(sensitive_payload) % 2 != 0:
            sensitive_payload += b"\x00"
        frame = AudioFrame(data=sensitive_payload)
        rep = repr(frame)
        assert "SECRET_VOICE_PAYLOAD" not in rep
        assert "AudioFrame" in rep
        assert f"bytes={len(sensitive_payload)}" in rep

    def test_create_silence_frame_helper(self):
        frame = create_silence_frame(duration_ms=30.0)
        assert frame.is_canonical() is True
        assert frame.data == b"\x00" * DEFAULT_BYTES_PER_FRAME
        assert all(b == 0 for b in frame.data)


# ============================================================================
# B. AudioRingBuffer Tests
# ============================================================================
class TestAudioRingBuffer:
    """Tests for AudioRingBuffer circular buffering and eviction mechanics."""

    def test_invalid_capacity_rejected(self):
        with pytest.raises(ValueError, match="max_frames must be > 0"):
            AudioRingBuffer(max_frames=0)

        with pytest.raises(ValueError, match="max_frames must be > 0"):
            AudioRingBuffer(max_frames=-5)

    def test_empty_buffer_state(self):
        buf = AudioRingBuffer(max_frames=5)
        assert len(buf) == 0
        assert buf.capacity == 5
        assert buf.is_empty() is True
        assert buf.is_full() is False
        assert buf.is_closed is False
        assert buf.dropped_frames == 0
        assert buf.total_written == 0
        assert buf.read() is None
        assert buf.peek() is None
        assert buf.read_many() == []
        assert buf.peek_recent() == []

    def test_write_and_read_single_frame(self):
        buf = AudioRingBuffer(max_frames=5)
        frame = create_silence_frame()
        res = buf.write(frame)
        assert res is True
        assert len(buf) == 1
        assert buf.is_empty() is False
        assert buf.is_full() is False
        assert buf.total_written == 1
        assert buf.dropped_frames == 0

        read_frame = buf.read()
        assert read_frame is frame
        assert len(buf) == 0
        assert buf.is_empty() is True

    def test_fifo_ordering(self):
        buf = AudioRingBuffer(max_frames=5)
        frames = [
            AudioFrame(data=f"FRAME_{i:02d}".encode("ascii") * 2)
            for i in range(5)
        ]
        for f in frames:
            buf.write(f)

        assert len(buf) == 5
        assert buf.is_full() is True

        for expected in frames:
            actual = buf.read()
            assert actual is expected

        assert buf.is_empty() is True

    def test_overflow_evicts_oldest_frame(self):
        # Capacity of 3: write A, B, C -> [A, B, C]
        # write D -> [B, C, D] (A evicted)
        buf = AudioRingBuffer(max_frames=3)
        fa = AudioFrame(data=b"\x01\x01")
        fb = AudioFrame(data=b"\x02\x02")
        fc = AudioFrame(data=b"\x03\x03")
        fd = AudioFrame(data=b"\x04\x04")

        assert buf.write(fa) is True
        assert buf.write(fb) is True
        assert buf.write(fc) is True
        assert len(buf) == 3
        assert buf.dropped_frames == 0

        # Overwrite: should return False (eviction occurred)
        assert buf.write(fd) is False
        assert len(buf) == 3
        assert buf.dropped_frames == 1
        assert buf.total_written == 4

        # Read order must be B, C, D
        assert buf.read() is fb
        assert buf.read() is fc
        assert buf.read() is fd
        assert buf.read() is None

    def test_multiple_overflows(self):
        buf = AudioRingBuffer(max_frames=2)
        frames = [AudioFrame(data=bytes([i, i])) for i in range(10)]

        for f in frames:
            buf.write(f)

        assert len(buf) == 2
        assert buf.dropped_frames == 8
        assert buf.total_written == 10

        # Buffer should retain frames 8 and 9
        assert buf.read() is frames[8]
        assert buf.read() is frames[9]
        assert buf.is_empty() is True

    def test_peek_does_not_remove(self):
        buf = AudioRingBuffer(max_frames=5)
        f1 = AudioFrame(data=b"\x01\x01")
        f2 = AudioFrame(data=b"\x02\x02")
        buf.write(f1)
        buf.write(f2)

        assert buf.peek() is f1
        assert len(buf) == 2
        assert buf.peek() is f1

        # read actually pops
        assert buf.read() is f1
        assert buf.peek() is f2
        assert len(buf) == 1

    def test_peek_recent(self):
        buf = AudioRingBuffer(max_frames=10)
        frames = [AudioFrame(data=bytes([i, i])) for i in range(6)]
        for f in frames:
            buf.write(f)

        # peek_recent(3) returns frames 3, 4, 5 in chronological order
        recent3 = buf.peek_recent(3)
        assert recent3 == [frames[3], frames[4], frames[5]]
        assert len(buf) == 6  # Does not mutate

        # count >= len returns all
        assert buf.peek_recent(10) == frames
        assert buf.peek_recent(None) == frames

        # count <= 0 returns empty
        assert buf.peek_recent(0) == []
        assert buf.peek_recent(-1) == []

    def test_read_many_partial_and_full(self):
        buf = AudioRingBuffer(max_frames=10)
        frames = [AudioFrame(data=bytes([i, i])) for i in range(5)]
        for f in frames:
            buf.write(f)

        # Drain 2 frames
        batch1 = buf.read_many(2)
        assert batch1 == [frames[0], frames[1]]
        assert len(buf) == 3

        # Drain remaining with None
        batch2 = buf.read_many(None)
        assert batch2 == [frames[2], frames[3], frames[4]]
        assert len(buf) == 0

        # Subsequent read_many returns empty list
        assert buf.read_many(5) == []

    def test_clear(self):
        buf = AudioRingBuffer(max_frames=5)
        buf.write(create_silence_frame())
        buf.write(create_silence_frame())
        assert len(buf) == 2

        buf.clear()
        assert len(buf) == 0
        assert buf.is_empty() is True
        assert buf.read() is None

    def test_close_behavior(self):
        buf = AudioRingBuffer(max_frames=5)
        f1 = create_silence_frame()
        buf.write(f1)

        buf.close()
        assert buf.is_closed is True

        # Writes to closed buffer must raise BufferClosedError
        with pytest.raises(BufferClosedError, match="closed"):
            buf.write(create_silence_frame())

        # Existing frames can still be read
        assert buf.read() is f1
        assert buf.read() is None

    def test_write_invalid_type_raises_type_error(self):
        buf = AudioRingBuffer(max_frames=5)
        with pytest.raises(TypeError, match="Expected AudioFrame"):
            buf.write("not_a_frame")  # type: ignore[arg-type]


# ============================================================================
# C. Concurrency Tests
# ============================================================================
class TestConcurrency:
    """Thread-safety verification using deterministic synchronization primitives."""

    def test_concurrent_writers_no_corruption(self):
        buf = AudioRingBuffer(max_frames=50)
        num_threads = 4
        frames_per_thread = 25
        start_event = threading.Event()

        def _worker(thread_id: int):
            start_event.wait(timeout=5.0)
            for i in range(frames_per_thread):
                # Unique 2-byte payload per write
                val = (thread_id * frames_per_thread + i) % 256
                buf.write(AudioFrame(data=bytes([val, val])))

        threads = [threading.Thread(target=_worker, args=(t,)) for t in range(num_threads)]
        for t in threads:
            t.start()

        start_event.set()
        for t in threads:
            t.join(timeout=5.0)
            assert not t.is_alive(), "Worker thread hung"

        assert buf.total_written == num_threads * frames_per_thread
        assert len(buf) == 50  # Capped at capacity
        assert buf.dropped_frames == (num_threads * frames_per_thread) - 50

    def test_concurrent_producer_consumer(self):
        buf = AudioRingBuffer(max_frames=100)
        total_items = 200
        consumed: List[AudioFrame] = []
        done_producing = threading.Event()

        def _producer():
            for i in range(total_items):
                val = i % 256
                buf.write(AudioFrame(data=bytes([val, val])))
            done_producing.set()

        def _consumer():
            while not done_producing.is_set() or not buf.is_empty():
                frame = buf.read()
                if frame is not None:
                    consumed.append(frame)
                else:
                    # Brief yield if buffer temporarily empty
                    time.sleep(0.001)

        t_prod = threading.Thread(target=_producer)
        t_cons = threading.Thread(target=_consumer)

        t_prod.start()
        t_cons.start()

        t_prod.join(timeout=5.0)
        t_cons.join(timeout=5.0)

        assert not t_prod.is_alive(), "Producer thread hung"
        assert not t_cons.is_alive(), "Consumer thread hung"
        # Total consumed + currently in buffer + dropped must equal total produced
        assert len(consumed) + buf.dropped_frames == total_items


# ============================================================================
# D. MockAudioCaptureProvider Tests
# ============================================================================
class TestMockAudioCaptureProvider:
    """Tests for MockAudioCaptureProvider lifecycle and injection interface."""

    def test_initial_state(self):
        provider = MockAudioCaptureProvider()
        assert provider.provider_name == "mock"
        assert provider.is_available() is True
        assert provider.is_running() is False
        assert provider.pushed_count == 0
        assert provider.get_pushed_frames() == []

    def test_start_stop_lifecycle_idempotent(self):
        provider = MockAudioCaptureProvider()
        assert provider.is_running() is False

        provider.start()
        assert provider.is_running() is True

        # Idempotent start
        provider.start()
        assert provider.is_running() is True

        provider.stop()
        assert provider.is_running() is False

        # Idempotent stop
        provider.stop()
        assert provider.is_running() is False

    def test_push_frame_while_stopped_raises(self):
        provider = MockAudioCaptureProvider()
        frame = create_silence_frame()
        with pytest.raises(RuntimeError, match="must be started"):
            provider.push_frame(frame)

    def test_push_frame_and_ring_buffer_delivery(self):
        ring_buf = AudioRingBuffer(max_frames=10)
        provider = MockAudioCaptureProvider(ring_buffer=ring_buf)
        provider.start()

        frame1 = create_silence_frame()
        frame2 = create_silence_frame()

        res1 = provider.push_frame(frame1)
        res2 = provider.push_frame(frame2)

        assert res1 is frame1
        assert res2 is frame2
        assert provider.pushed_count == 2
        assert len(ring_buf) == 2
        assert ring_buf.read() is frame1
        assert ring_buf.read() is frame2

    def test_push_pcm_helper(self):
        provider = MockAudioCaptureProvider()
        provider.start()

        data = b"\x05\x05" * 480
        frame = provider.push_pcm(data)

        assert frame.data == data
        assert frame.sample_rate == DEFAULT_SAMPLE_RATE
        assert frame.channels == DEFAULT_CHANNELS
        assert frame.sample_width == DEFAULT_SAMPLE_WIDTH
        assert provider.pushed_count == 1

    def test_push_silence_helper(self):
        provider = MockAudioCaptureProvider()
        provider.start()

        frame = provider.push_silence(duration_ms=30.0)
        assert frame.is_canonical() is True
        assert len(frame.data) == DEFAULT_BYTES_PER_FRAME
        assert all(b == 0 for b in frame.data)
        assert provider.pushed_count == 1

    def test_clear(self):
        provider = MockAudioCaptureProvider()
        provider.start()
        provider.push_silence()
        assert provider.pushed_count == 1

        provider.clear()
        assert provider.pushed_count == 0
        assert provider.get_pushed_frames() == []

    def test_interface_compliance(self):
        provider = MockAudioCaptureProvider()
        assert isinstance(provider, EVAudioCaptureProvider)


# ============================================================================
# E. Privacy & Safety Tests
# ============================================================================
class TestPrivacyAndSafety:
    """Verifies that no files or audio persistence occurs during operation."""

    def test_zero_disk_writes(self, tmp_path):
        # Capture directory file list before operations
        before_files = set(os.listdir("."))

        buf = AudioRingBuffer(max_frames=10)
        provider = MockAudioCaptureProvider(ring_buffer=buf)
        provider.start()

        for _ in range(20):
            provider.push_silence(duration_ms=30.0)

        frames = buf.read_many()
        assert len(frames) == 10

        after_files = set(os.listdir("."))
        new_files = after_files - before_files
        assert not new_files, f"Unexpected disk files created: {new_files}"
