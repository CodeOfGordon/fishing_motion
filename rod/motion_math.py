import math
from dataclasses import dataclass, astuple

ACCEL_LSB_PER_G = 16384.0
GYRO_LSB_PER_DPS = 131.0
MAX_TILT_ANGLE = 45
TILT_ZERO_ANGLE = 7
DT = 0.016

@dataclass
class RawMotionData():
    # where y is pting forward, and x is sideways, and z is up/down
    ax: int
    ay: int
    az: int
    gx: int
    gy: int
    gz: int

@dataclass
class MotionData():
    # where y is pting forward, and x is sideways, and z is up/down
    ax: float
    ay: float
    az: float
    gx: float
    gy: float
    gz: float


def raw_to_g(raw):
    '''Accelerometer counts to g (default +-2 g range).'''
    return raw / ACCEL_LSB_PER_G


def raw_to_dps(raw):
    '''Gyroscope counts to degrees per second (default +-250 deg/s range).'''
    return raw / GYRO_LSB_PER_DPS


def parse_line(line) -> tuple[int, int, int, int, int, int, int] | None:
    '''"ax,ay,az,gx,gy,gz" -> (ax_g, ay_g, az_g, gx_dps, gy_dps, gz_dps), or None if malformed.'''
    parts = line.strip().split(",")
    if len(parts) != 6:
        return None
    try:
        ax, ay, az, gx, gy, gz = (int(p) for p in parts)
    except ValueError:
        return None
    return (raw_to_g(ax), raw_to_g(ay), raw_to_g(az),
            raw_to_dps(gx), raw_to_dps(gy), raw_to_dps(gz))


def filter(motion: MotionData, previous: MotionData | None, alpha: float = 0.5) -> MotionData:
    '''
    EMA smoothing: small alpha => smoother but laggier
    '''
    if previous is None:
        return motion
    return MotionData(*(p + alpha * (x - p) for p, x in zip(astuple(previous), astuple(motion))))


def gyro_bias(still: list[MotionData]) -> tuple[float, float, float]:
    '''
    average gyro while held still => subtract from later samples
    '''
    n = len(still)
    return (sum(m.gx for m in still) / n, sum(m.gy for m in still) / n, sum(m.gz for m in still) / n)


def clamp(num, low, high):
    '''forces low <= num <= high'''
    return max(low, min(num, high))


def magnitude(motion: MotionData) -> float:
    return math.sqrt(motion.ax ** 2 + motion.ay ** 2 + motion.az ** 2)


def accel_angle(motion: MotionData) -> float:
    '''
    roll angle from gravity, in degrees
    '''
    return math.degrees(math.atan2(-motion.ax, motion.az))


def angle_to_tilt(angle: float, zero: float = TILT_ZERO_ANGLE) -> float:
    return clamp((angle - zero) / MAX_TILT_ANGLE, -1, 1)


def follow_level(history: list[MotionData], zero: float) -> float:
    '''
    drift the level (zero) toward the angle you rest at: only after 1 s of stillness, and only if it is near the current zero
    '''
    STILL_DPS = 30
    STILL_SAMPLES = 62
    NEAR_ANGLE = 12
    FOLLOW_RATE = 0.01
    recent = history[-STILL_SAMPLES:]
    if len(recent) < STILL_SAMPLES or any(max(abs(m.gx), abs(m.gy), abs(m.gz)) > STILL_DPS for m in recent):
        return zero
    rest = sum(accel_angle(m) for m in recent) / len(recent)
    if abs(rest - zero) > NEAR_ANGLE:
        return zero
    return zero + FOLLOW_RATE * (rest - zero)


def tilt(history: list[MotionData], zero: float = TILT_ZERO_ANGLE) -> float:
    '''
    angle of title => how fast to tilt [-1,1]
    gyro carries the angle, accel corrects it only while the rod isn't being swung (|a| close to 1 g)
    '''
    angle = accel_angle(history[0])
    for m in history[1:]:
        if 0.8 < magnitude(m) < 1.2:
            angle = fuse_angle(angle, m.gy, accel_angle(m), DT)
        else:
            angle += m.gy * DT
    return angle_to_tilt(angle, zero)


def fuse_angle(angle: float, gy: float, accel: float, dt: float) -> float:
    '''
    complementary filter: gyro for short term, accel for long term. gy = roll rate minus bias
    '''
    return 0.98 * (angle + gy * dt) + 0.02 * accel


def gesture(history: list[MotionData]) -> list[tuple[int, float]]:
    '''
    the swing that just went calm on this sample => its gx pushes as (+1 or -1, degrees swung), else []
    '''
    SPIN_DPS = 60
    SETTLE_SAMPLES = 16
    MIN_SAMPLES = 4
    MAX_SAMPLES = 100
    end = len(history) - SETTLE_SAMPLES
    if end < 1 or abs(history[end - 1].gx) <= SPIN_DPS or any(abs(m.gx) > SPIN_DPS for m in history[end:]):
        return []
    i = end - 1
    calm = 0
    while i >= 0 and calm < SETTLE_SAMPLES:
        calm = calm + 1 if abs(history[i].gx) <= SPIN_DPS else 0
        i -= 1
    run = history[i + 1:end]
    if len(run) > MAX_SAMPLES:
        return []
    pushes = []
    sign, count, angle = 0, 0, 0.0
    for m in run + [None]:
        now = 0 if m is None or abs(m.gx) <= SPIN_DPS else (1 if m.gx > 0 else -1)
        if now != sign:
            if sign != 0 and count >= MIN_SAMPLES:
                pushes.append((sign, angle))
            sign, count, angle = now, 0, 0.0
        if now != 0:
            count += 1
            angle += abs(m.gx) * DT
    return pushes


def cast(history: list[MotionData]) -> float | None:
    '''
    swing forward and down (gx negative) then the rod bounces back (gx positive) => cast action strength [0,1]
    a wind-up (gx positive just before the swing down) adds to it: wind up for a far cast
    '''
    MIN_ANGLE = 12
    MAX_ANGLE = 55
    pushes = gesture(history)
    for i, ((first, down), (second, up)) in enumerate(zip(pushes, pushes[1:])):
        if first < 0 < second and down >= MIN_ANGLE and up >= MIN_ANGLE:
            wind = pushes[i - 1][1] if i > 0 and pushes[i - 1][0] > 0 else 0.0
            return clamp((down + wind - MIN_ANGLE) / (MAX_ANGLE - MIN_ANGLE), 0, 1)
    return None


def hook_set(history: list[MotionData]) -> float | None:
    '''
    Jerk upwards (gx positive first, no cast after it; the hand coming back is ignored) => hook the fish (i.e. is what activates going into the reeling fish in phase)
    '''
    MIN_ANGLE = 12
    MAX_ANGLE = 40
    big = [push for push in gesture(history) if push[1] >= MIN_ANGLE]
    if big and big[0][0] > 0 and cast(history) is None:
        return clamp((big[0][1] - MIN_ANGLE) / (MAX_ANGLE - MIN_ANGLE), 0, 1)
    return None


def reel(history: list[MotionData]) -> float:
    '''
    Rotate in circles (3+ big turns of gx in the last 1.2 s, averaged) => reel in speed [0,1]
    '''
    MAX_TURNS_PER_S = 4
    DEADBAND = 60
    RECENT_SAMPLES = 75
    crossings = []
    below = False
    for i, m in enumerate(history):
        if m.gx < -DEADBAND:
            below = True
        elif m.gx > DEADBAND and below:
            crossings.append(i)
            below = False
    recent = [c for c in crossings if c >= len(history) - RECENT_SAMPLES]
    if len(recent) < 3:
        return 0.0
    period = (recent[-1] - recent[0]) / (len(recent) - 1) * DT
    if (len(history) - 1 - recent[-1]) * DT > 1.5 * period:
        return 0.0
    return clamp(1 / period / MAX_TURNS_PER_S, 0, 1)
