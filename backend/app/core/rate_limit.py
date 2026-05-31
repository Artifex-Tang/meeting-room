import threading
import time

from fastapi import HTTPException

_lock = threading.Lock()
_counters: dict[str, tuple[float, int]] = {}


def check_rate(key: str, limit: int, window: int = 60) -> None:
    """Raise 429 if key has exceeded limit hits within window seconds."""
    now = time.time()
    with _lock:
        start, count = _counters.get(key, (now, 0))
        if now - start >= window:
            start, count = now, 0
        count += 1
        _counters[key] = (start, count)
    if count > limit:
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后重试")
