"""The rod's MotionSource: the bridge between the Nano and the game.

This file belongs to the rod side of the project (firmware, serial reader,
gesture and reel-rate detection, ML). The goal here is that you UNDERSTAND
every line, not that you type it all by hand. Use docs, examples and an AI
assistant freely, but be able to explain each piece back:

* What flows where? The Nano streams "ax,ay,az,gx,gy,gz\\n" lines in. The
  game pulls the newest state out with poll() and drain_events(). The game
  pushes messages like "BITE\\n" back out with send().
* Why is each pyserial call there? Serial(port, baud) opens the port and sets
  the speed once; read()/in_waiting get bytes in; write() sends bytes out;
  close() releases it. Bytes are not lines, so you split on b"\\n" yourself.
* Why does poll() never block? It runs once per frame on the game thread.
* What happens when something goes wrong? A bad line is skipped, a silent
  Nano means connected=False, and an __init__ error makes the factory fall
  back to the keyboard with a message.

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

Practical notes for macOS and the Arduino Nano:

* Open the ``/dev/cu.*`` port, not ``/dev/tty.*``. A Nano shows up as
  ``/dev/cu.usbserial-*`` (or ``/dev/cu.wchusbserial*`` on CH340 clones).
* The Nano resets when the port opens, so expect about 2 s with no data.
* The game assumes 115200 baud by default (Settings can change it).
* Reeling must show no visible lag: keep your reel-rate estimate's latency
  under about 40 ms. A long analysis window adds visible lag.
* ``poll()`` runs on the game thread once per frame (60-120 times a second),
  so heavy work (for example running a model on every sample) belongs elsewhere.

Test your implementation against the contract with:

    ROD_PORT=/dev/cu.usbserial-XXXX pytest -m rod
"""
from __future__ import annotations
import time
import glob
import collections

from fishing.input.motion import CAST, HOOK_SET, MotionEvent, MotionState, now_ms
from rod.motion_math import parse_line, MotionData
import rod.motion_math as motion_math
import serial


class SerialMotionSource:
    """Reads the rod over USB serial. STUB: yours to implement."""

    def __init__(self, port: str, baud: int = 115200) -> None:
      if port == "":
        matches = sorted(glob.glob("/dev/cu.usbserial-*") + glob.glob("/dev/cu.wchusbserial*"))
        if not matches:
          raise RuntimeError("No Nano found: is it plugged in? (looked for /dev/cu.usbserial-* and /dev/cu.wchusbserial*)")
        port = matches[0]

      self._connection = serial.Serial(port, baud, timeout=0)
      self._buf = b""
      self._seq = 0
      self._tilt_zero = motion_math.TILT_ZERO_ANGLE
      self._state = MotionState(t_ms=now_ms(), reel_rate=0, tilt=0, connected=False)
      self._filtered_history = collections.deque(maxlen=200)
      self._motion_history = collections.deque(maxlen=200)
      self._events = collections.deque(maxlen=200)
      print('Connection made')
      self.test()

    def test(self):
      text = self._connection.read_all().decode(errors="ignore") # bytes -> str
      for line in text.split("\n")[:-1]:
        print(parse_line(line))

    def poll(self) -> MotionState:
      self._buf += self._connection.read_all()
      parts = self._buf.split(b"\n")
      self._buf = parts[-1]
      for part in parts[:-1]:
        values = parse_line(part.decode(errors="ignore"))
        if values is None:
          continue
        self.add_sample(MotionData(*values))
      return self._state

    def add_sample(self, motion: MotionData) -> None:
      self._seq += 1
      previous = None
      if self._filtered_history:
        previous = self._filtered_history[-1]
      filtered = motion_math.filter(motion, previous)
      self._filtered_history.append(filtered)
      self._motion_history.append(motion)
      reel_rate_ = motion_math.reel(list(self._filtered_history))
      self._tilt_zero = motion_math.follow_level(list(self._motion_history), self._tilt_zero)
      tilt_ = motion_math.tilt(list(self._motion_history), self._tilt_zero)
      self._state = MotionState(
        t_ms=now_ms(),
        reel_rate=reel_rate_,
        tilt=tilt_,
        connected=True,
        seq=self._seq,
      )
      cast_strength = motion_math.cast(list(self._motion_history))
      if cast_strength is not None:
        self._events.append(MotionEvent(CAST, now_ms(), cast_strength))
      hook_strength = motion_math.hook_set(list(self._motion_history))
      if hook_strength is not None:
        self._events.append(MotionEvent(HOOK_SET, now_ms(), hook_strength))

    def drain_events(self) -> list[MotionEvent]:
      events = list(self._events)
      self._events.clear()
      return events

    def send(self, msg: str) -> None:
      self._connection.write((msg + "\n").encode())

    def close(self) -> None:
      self._connection.close()
