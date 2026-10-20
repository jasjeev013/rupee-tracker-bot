from app.backend.ratelimit import RateLimiter


def test_limiter_blocks_then_window_expires():
    now = [0.0]
    rl = RateLimiter(2, 60, clock=lambda: now[0])
    assert rl.allow(1) and rl.allow(1)
    assert not rl.allow(1)
    assert rl.allow(2)  # other users unaffected
    now[0] = 61
    assert rl.allow(1)
