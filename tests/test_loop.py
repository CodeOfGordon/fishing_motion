from fishing.loop import FixedStep, deliver

STEP = 1 / 60


def make():
    return FixedStep(STEP, max_frame_s=0.25, max_steps=5)


def test_exact_frames_give_one_step_each():
    fs = make()
    assert [fs.advance(STEP) for _ in range(10)] == [1] * 10


def test_irregular_frames_keep_total_time():
    fs = make()
    frames = [0.010, 0.020, 0.007, 0.030, 0.016, 0.017] * 20
    steps = sum(fs.advance(f) for f in frames)
    expected = sum(frames) / STEP
    assert abs(steps - expected) < 1.0


def test_fast_display_runs_zero_steps_some_frames():
    fs = make()
    steps = [fs.advance(1 / 144) for _ in range(144)]
    assert 0 in steps
    assert abs(sum(steps) - 60) <= 1


def test_hitch_is_clamped_and_backlog_dropped():
    fs = make()
    assert fs.advance(2.0) == 5  # capped at max_steps
    assert fs.acc < STEP  # backlog dropped, no fast-forward next frame
    assert fs.advance(STEP) == 1


def test_negative_frame_time_is_ignored():
    fs = make()
    assert fs.advance(-1.0) == 0


def test_deliver_gives_events_to_first_step_only():
    got = []
    leftover = deliver(3, ["a", "b"], lambda evs: got.append(list(evs)))
    assert got == [["a", "b"], [], []]
    assert leftover == []


def test_deliver_carries_inbox_over_zero_step_frames():
    got = []
    inbox = deliver(0, ["a"], lambda evs: got.append(evs))
    assert got == [] and inbox == ["a"]
    inbox = deliver(1, inbox + ["b"], lambda evs: got.append(list(evs)))
    assert got == [["a", "b"]] and inbox == []


def test_every_event_delivered_exactly_once_under_jitter():
    fs = make()
    seen = []
    inbox = []
    frames = [0.004, 0.030, 0.001, 0.016, 0.0, 0.050] * 50
    for i, f in enumerate(frames):
        inbox.append(i)
        inbox = deliver(fs.advance(f), inbox, seen.extend)
    seen.extend(inbox)  # whatever is still waiting would go to the next step
    assert seen == list(range(len(frames)))
