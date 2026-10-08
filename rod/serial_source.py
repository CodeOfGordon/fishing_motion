"""The rod's MotionSource — YOURS TO WRITE.

╔══════════════════════════════════════════════════════════════════════╗
║  STUB. This file belongs to the rod side of the project (firmware,  ║
║  serial reader, gesture and reel-rate detection, ML). The game only ║
║  defines the contract below; every method raises NotImplementedError ║
║  until you implement it.                                             ║
╚══════════════════════════════════════════════════════════════════════╝

Contract the game relies on (see fishing/input/motion.py):

* ``poll()`` returns the newest ``MotionState`` immediately. It never blocks
  and never returns None. Before the first sample arrives, and after a
  dropout, report ``connected=False``.
* ``drain_events()`` returns every ``MotionEvent`` ("cast", "hook_set",
  optionally "bite_ack") since the previous call, oldest first. Continuous
  values are newest-wins, but one-shot gestures must be queued, never
  overwritten.
* Stamp states and events with ``now_ms()`` from fishing.input.motion (the
  host clock). For a gesture, use the time of its peak sample.
* ``send(msg)`` must not block. The game calls ``send("BITE")`` exactly once
  per bite.
* ``close()`` releases the serial port, so the source can be switched in
  Settings and reopened later.

Practical notes for macOS and the Uno:

* Open ``/dev/cu.usbmodem*``, not ``/dev/tty.*``.
* The Uno resets when the port opens, so expect about 2 s with no data.
* The game assumes 115200 baud by default (Settings can change it).
* Reeling must show no visible lag: keep your reel-rate estimate's latency
  under about 40 ms. A long analysis window adds visible lag.
* ``poll()`` runs on the game thread 60 times a second, so heavy work (for
  example running a model on every sample) belongs elsewhere.

Test your implementation against the contract with:

    ROD_PORT=/dev/cu.usbmodemXXXX pytest -m rod
"""
from __future__ import annotations

from fishing.input.motion import MotionEvent, MotionState


class SerialMotionSource:
    """Reads the rod over USB serial. STUB: yours to implement."""

    def __init__(self, port: str, baud: int = 115200) -> None:
        raise NotImplementedError(
            "rod.serial_source.SerialMotionSource is a stub for you to implement"
        )

    def poll(self) -> MotionState:
        raise NotImplementedError

    def drain_events(self) -> list[MotionEvent]:
        raise NotImplementedError

    def send(self, msg: str) -> None:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError
