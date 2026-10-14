import argparse
import re
import struct
from pathlib import Path

LOW, HIGH = 55, 96
BUZZER_CPP = Path(__file__).resolve().parent.parent / "src" / "buzzer.cpp"


def read_vlq(data, i):
    value = 0
    while True:
        byte = data[i]
        i += 1
        value = (value << 7) | (byte & 0x7F)
        if not byte & 0x80:
            return value, i


def read_track(data, i, end):
    '''One MTrk body -> (notes as (start_tick, end_tick, pitch), tempos as (tick, us_per_beat)).'''
    tick, status, held, notes, tempos = 0, 0, {}, [], []
    while i < end:
        delta, i = read_vlq(data, i)
        tick += delta
        if data[i] & 0x80:
            status = data[i]
            i += 1
        if status == 0xFF:
            kind = data[i]
            size, i = read_vlq(data, i + 1)
            if kind == 0x51:
                tempos.append((tick, int.from_bytes(data[i:i + size], "big")))
            i += size
        elif status in (0xF0, 0xF7):
            size, i = read_vlq(data, i)
            i += size
        else:
            size = 1 if status & 0xF0 in (0xC0, 0xD0) else 2
            pitch, velocity = data[i], data[i + 1] if size == 2 else 0
            i += size
            if status & 0xF0 == 0x90 and velocity:
                held[pitch] = tick
            elif status & 0xF0 in (0x80, 0x90) and pitch in held:
                notes.append((held.pop(pitch), tick, pitch))
    return sorted(notes), tempos


def read_midi(path):
    '''-> (ticks per beat, tempos, one note list per track).'''
    data = path.read_bytes()
    track_count, ticks_per_beat = struct.unpack(">HH", data[10:14])
    i, tracks, tempos = 14, [], []
    for _ in range(track_count):
        size = struct.unpack(">I", data[i + 4:i + 8])[0]
        notes, track_tempos = read_track(data, i + 8, i + 8 + size)
        tracks.append(notes)
        tempos += track_tempos
        i += 8 + size
    return ticks_per_beat, sorted(tempos) or [(0, 500000)], tracks


def tick_to_ms(tick, ticks_per_beat, tempos):
    ms, last, us = 0.0, 0, 500000
    for start, tempo in tempos:
        if start >= tick:
            break
        ms += (start - last) * us / ticks_per_beat / 1000
        last, us = start, tempo
    return ms + (tick - last) * us / ticks_per_beat / 1000


def fold(pitch):
    '''Move a pitch by octaves into the range the buzzer plays well.'''
    while pitch < LOW:
        pitch += 12
    while pitch > HIGH:
        pitch -= 12
    return pitch


def hz(pitch):
    return round(440 * 2 ** ((pitch - 69) / 12))


def melody(notes, ticks_per_beat, tempos, seconds):
    '''The highest sounding note at each moment, as (hz, ms); 0 is a rest.'''
    ticks = sorted({t for start, stop, _ in notes for t in (start, stop)})
    line = []
    for a, b in zip(ticks, ticks[1:]):
        start = tick_to_ms(a, ticks_per_beat, tempos)
        stop = min(tick_to_ms(b, ticks_per_beat, tempos), seconds * 1000)
        if start >= seconds * 1000:
            break
        sounding = [p for s, e, p in notes if s <= a < e]
        freq = hz(fold(max(sounding))) if sounding else 0
        if round(stop - start) > 0:
            line.append((freq, round(stop - start)))
    return line


def patch_buzzer(line):
    rows = "\n".join(f"  {{{freq}, {ms}}}," for freq, ms in line)
    source = BUZZER_CPP.read_text()
    pattern = re.compile(r"(// BEGIN END_TUNE\n).*?(// END END_TUNE)", re.S)
    BUZZER_CPP.write_text(pattern.sub(lambda m: m.group(1) + rows + "\n" + m.group(2), source))


def main():
    parser = argparse.ArgumentParser(description="MIDI track -> END_TUNE[] in src/buzzer.cpp")
    parser.add_argument("midi", type=Path)
    parser.add_argument("--track", type=int, help="leave out to list the tracks")
    parser.add_argument("--seconds", type=float, default=15.0)
    parser.add_argument("--write", action="store_true", help="patch buzzer.cpp instead of printing")
    args = parser.parse_args()

    ticks_per_beat, tempos, tracks = read_midi(args.midi)
    if args.track is None:
        for i, notes in enumerate(tracks):
            if notes:
                print(f"track {i}: {len(notes)} notes, pitches {min(n[2] for n in notes)}..{max(n[2] for n in notes)}")
        return
    line = melody(tracks[args.track], ticks_per_beat, tempos, args.seconds)
    print(f"{len(line)} notes, {sum(ms for _, ms in line) / 1000:.1f} s")
    if args.write:
        patch_buzzer(line)


main()
