import math

from rod.motion_math import MotionData, accel_angle, follow_level


def still(angle_deg, n=62):
    a = math.radians(angle_deg)
    return [MotionData(-math.sin(a), 0.0, math.cos(a), 0.0, 0.0, 0.0) for _ in range(n)]


def test_level_drifts_toward_where_you_rest():
    assert 7 < follow_level(still(12), 7) < 12


def test_level_ignores_a_moving_rod():
    moving = still(12)
    moving[-1] = MotionData(0.0, 0.0, 1.0, 0.0, 200.0, 0.0)
    assert follow_level(moving, 7) == 7


def test_level_ignores_a_deliberate_tilt():
    assert follow_level(still(40), 7) == 7


def test_level_needs_a_full_second_of_stillness():
    assert follow_level(still(12, n=30), 7) == 7


from rod.motion_math import cast, hook_set


def swing_history(*pushes):
    """Calm, the pushes (gx value, samples) with a short gap between, then exactly the 16 calm samples that end a swing."""
    gx = [0.0] * 20
    for value, samples in pushes:
        gx += [value] * samples + [0.0] * 3
    gx = gx[:-3] + [0.0] * 16
    return [MotionData(0.0, 0.0, 1.0, g, 0.0, 0.0) for g in gx]


def test_a_wind_up_makes_a_stronger_cast():
    plain = cast(swing_history((-250, 10), (200, 15)))
    wound_up = cast(swing_history((200, 12), (-250, 10), (200, 15)))
    assert plain is not None and wound_up is not None
    assert wound_up > plain


def test_a_wound_up_cast_is_not_a_hook_set():
    history = swing_history((200, 12), (-250, 10), (200, 15))
    assert hook_set(history) is None
