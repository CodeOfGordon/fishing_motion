# Rod Fishing

A Wii Play-style fishing game played with a real rod: an MPU-6050 on a ruler, read by an
Arduino Uno and streamed over USB serial. It's fully playable with keyboard and mouse too.

Cast, steer the lure, wait out the nibbles, strike on the real bite, then win a short reel fight
before the 3-minute clock runs out.

## Setup (macOS)
```sh
brew install python@3.12
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

## Run
```sh
python -m fishing                       # fullscreen; F11 toggles
python -m fishing --windowed            # in a window
python -m fishing --windowed --practice # straight into Practice
python -m fishing --source rod          # use the rod for this run (Settings saves the choice)
python -m fishing --seed 42             # repeatable rounds
```

## Modes
- **Play:** a 3:00 round. Score, medal and an accuracy panel at the end.
- **Practice:** no clock and the debug overlay is on. **B** makes the nearest fish bite (tests the
  buzzer and the hook-set). **K** brings out the Lantern Koi.
- **Rod Test:** 10 cast prompts, then 10 bites. Scores your pass criteria: casts registered,
  hook-sets registered, and BITE acks.
- **Settings:** input source, serial port (with Scan), baud, tilt/reel sensitivity and dead zones,
  tilt smoothing, invert, recentre, difficulty, forgiving hook-set, volumes, game bite sound,
  simulated buzzer. Saved to `data/settings.json`.
- **High Scores:** top 10, saved to `data/highscores.json`.

## Keyboard and mouse
| Input | Action |
|---|---|
| Space (hold, release) | Cast; hold longer for distance |
| Circle the mouse around the window centre | Reel (analog) |
| W / S (hold) | Reel fast / slow |
| A D or ← → | Tilt: aim the cast, steer the lure, lean against a running fish |
| Left click, J or ↑ | Set the hook |
| Esc | Pause (in a round) / back |
| F3 | Debug overlay: fps, input rate and age, reel/tilt, last gesture, a 3 s graph |
| F11 | Fullscreen |

With the rod in menus: tilt to move the selection, hook-set to choose.

## How a cast plays
1. **Aim and flick.** Tilt aims the cast, and flick strength sets the distance (shallow, mid or deep
   water).
2. **Reel slowly.** A slow retrieve attracts fish; a fast one spooks the wary ones. Fish only notice a
   lure in front of them.
3. **Nibbles are fake.** The bobber twitches and the game stays quiet. Striking now is **too early**.
4. **The real bite** pulls the bobber under with a splash, the game sends `BITE` (the Uno beeps), and
   you have about half a second to a second to jerk.
5. **The fight:** reel when the fish rests, ease off when it runs, and lean the rod (tilt) against
   its run. Too tight and the line snaps; too slack and it shakes the hook.

Watch for the **Bait Thief**: it drags the bobber sideways instead of sinking it, and hooking it
costs points. The **BONUS** fish (top right) scores double.

## Plugging in the rod
The game talks to any `MotionSource` (`fishing/input/motion.py`). The rod's source is
`rod/serial_source.py`. It's a stub for you to implement; its docstring lists the contract. Check
your implementation with:
```sh
ROD_PORT=/dev/cu.usbmodemXXXX pytest -m rod
```
Then choose **Settings > Input > Rod**, set the port (or use **Scan**), and pick **Connect**. If the
rod can't start, the game says why and stays on keyboard.

## Firmware (`firmware/`)
The Arduino Nano's code is a [PlatformIO](https://platformio.org) project. Open the `firmware/`
folder in VS Code with the PlatformIO extension. The firmware itself is `firmware/src/main.cpp`.

| Button (VS Code bottom bar) | Does | Command line |
|---|---|---|
| ✓ Build | compile the firmware | `pio run` |
| → Upload | compile and flash the Nano over USB | `pio run -t upload` |
| 🔌 Serial Monitor | show what the Nano prints, and send it text (115200 baud) | `pio device monitor` |

Only one program can use the USB port at a time. Close the Serial Monitor before uploading or
before starting the game with the rod.

## Logs
Each launch writes `logs/session_YYYY-MM-DD_HHMMSS.csv`, one row per event, flushed as it goes.

Columns: `wall_iso, t_ms, round_id, mode, input, state, event, accepted, reason, bite_id, species,
strength, value, detail`.

The rows that matter for the pass criteria:

| Event | Meaning |
|---|---|
| `cast` | `accepted` 1/0, with the reason it was ignored |
| `bite` | `detail.send` shows whether `BITE` was sent |
| `bite_ack` | if your firmware replies `ACK` |
| `hook_attempt` | `reason`: hooked, early, late, no_bite or ignored |
| `catch` | a fish landed |
| `escape` | a fish lost, with the reason |
| `rodtest_*` | Rod Test results |

## Development
```sh
pytest                                  # headless: no window, no sound device needed
python tools/simulate_rounds.py -n 200  # bot rounds: catches, score spread, medal suggestions
```
- **Tuning:** every gameplay number lives in `config/tuning.toml`.
- **Visual constants:** in `fishing/render/palette.py`.
- **Credits:** asset credits are in `CREDITS.md`, and a test checks every asset file is listed.
