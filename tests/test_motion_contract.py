"""Every MotionSource must meet the boundary contract in fishing/input/motion.py.

Run against your rod too:  ROD_PORT=/dev/cu.usbserial-XXXX pytest -m rod
"""
import os
import time

import pytest

from fishing.input.keyboard_mouse import KeyboardMouseSource
from fishing.input.motion import MotionEvent, MotionSource, MotionState
from fishing.input.scripted import Keyframe, ScriptedSource

FAST_MS = 2.0


def scripted(_tuning):
    return ScriptedSource(
        keyframes=[Keyframe(0, 0.5, -0.3)],
        events=[MotionEvent("cast", 0, 0.7)],
    )


def keyboard(tuning):
    return KeyboardMouseSource(tuning.keyboard, centre=(640, 360), is_down=lambda k: False)


def rod(_tuning):
    port = os.environ.get("ROD_PORT")
    if not port:
        pytest.skip("set ROD_PORT to test your SerialMotionSource")
    from rod.serial_source import SerialMotionSource

    return SerialMotionSource(port, int(os.environ.get("ROD_BAUD", "115200")))


SOURCES = [
    pytest.param(scripted, id="scripted"),
    pytest.param(keyboard, id="keyboard"),
    pytest.param(rod, id="rod", marks=pytest.mark.rod),
]


@pytest.fixture(params=SOURCES)
def source(request, tuning):
    src = request.param(tuning)
    yield src
    src.close()


def timed(fn):
    t0 = time.perf_counter()
    out = fn()
    return out, (time.perf_counter() - t0) * 1000.0


def test_is_a_motion_source(source):
    assert isinstance(source, MotionSource)


def test_poll_never_none_fast_and_in_range(source):
    for _ in range(50):
        st, ms = timed(source.poll)
        assert isinstance(st, MotionState)
        assert ms < FAST_MS, f"poll() took {ms:.2f} ms"
        assert 0.0 <= st.reel_rate <= 1.0
        assert -1.0 <= st.tilt <= 1.0
        assert isinstance(st.connected, bool)


def test_seq_never_decreases(source):
    seqs = [source.poll().seq for _ in range(20)]
    assert seqs == sorted(seqs)


def test_drain_events_empties_and_is_ordered(source):
    events, ms = timed(source.drain_events)
    assert ms < FAST_MS
    assert all(isinstance(e, MotionEvent) for e in events)
    assert [e.t_ms for e in events] == sorted(e.t_ms for e in events)
    assert all(e.kind in ("cast", "hook_set", "bite_ack") for e in events)
    assert source.drain_events() == []


def test_send_does_not_block(source):
    _, ms = timed(lambda: source.send("BITE"))
    assert ms < FAST_MS


def test_close_is_idempotent(source):
    source.close()
    source.close()
