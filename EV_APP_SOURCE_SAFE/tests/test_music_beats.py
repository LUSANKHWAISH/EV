"""Known musical attacks should trigger once; steady audio must not keep pulsing."""
import numpy as np
import pytest

from music.onsets import BeatEnvelope,OnsetDetector


def fixture(rate=48000):
    t=np.arange(rate*5)/rate
    signal=np.zeros_like(t)
    expected=[.35,.85,1.35,1.85,2.35,2.85,3.35,3.85]
    for onset in expected:
        age=t-onset
        envelope=np.where(age>=0,np.exp(-np.maximum(age,0)*32),0)
        signal+=.4*np.sin(2*np.pi*75*age)*envelope
    return signal,expected


def detected(signal,rate,block_size):
    detector=OnsetDetector(rate);found=[]
    for start in range(0,len(signal),block_size):
        for offset,strength,rms in detector.process(signal[start:start+block_size]):
            found.append(((start+offset)/rate,strength,rms))
    return found


@pytest.mark.parametrize('rate',[44100,48000])
@pytest.mark.parametrize('block_size',[512,1024,4096])
def test_each_kick_triggers_once_for_capture_and_decoder_blocks(rate,block_size):
    pcm,expected=fixture(rate)
    hits=detected(pcm,rate,block_size)
    assert len(hits)==len(expected),(expected,hits)
    assert all(0<=actual[0]-goal<.05 for actual,goal in zip(hits,expected))
    assert all(.4<=hit[1]<=1 for hit in hits)


def test_silence_never_triggers():
    assert detected(np.zeros(48000*3),48000,4096)==[]


def test_sustained_tone_does_not_repeat_after_its_attack():
    t=np.arange(48000*3)/48000
    hits=detected(.25*np.sin(2*np.pi*750*t),48000,4096)
    assert len(hits)==1 and hits[0][0]<.04,hits


def test_short_attack_in_first_half_of_large_decoder_buffer_is_not_lost():
    pcm=np.zeros(8192);t=np.arange(800)/48000
    pcm[100:900]=.6*np.sin(2*np.pi*2000*t)*np.exp(-t*300)
    hits=detected(pcm,48000,4096)
    assert len(hits)==1 and hits[0][0]<.03,hits


def test_nonfinite_input_does_not_create_beats():
    pcm=np.zeros(4096);pcm[5]=np.nan;pcm[20]=np.inf
    assert detected(pcm,48000,4096)==[]


def test_envelope_releases_and_does_not_restart_itself():
    envelope=BeatEnvelope()
    assert envelope.update(.033,[{'strength':1,'rms':.1}],1,True)==1
    for _ in range(30):envelope.update(.033,[],1,True)
    assert envelope.value==0


@pytest.mark.parametrize('gain,active',[(0,True),(1,False)])
def test_mute_pause_or_stale_source_clears_pulse(gain,active):
    envelope=BeatEnvelope();envelope.value=1
    assert envelope.update(.03,[{'strength':1,'rms':.1}],gain,active)==0
