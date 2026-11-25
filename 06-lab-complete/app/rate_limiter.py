"""
Rate limiting (tiêu chí 7).

  • Mỗi API key tối đa RATE_LIMIT_PER_MINUTE request trong 60 giây (sliding window).
  • Vượt giới hạn → HTTP 429 kèm header Retry-After.
  • State lưu trong Redis (sorted set) → mọi worker / instance dùng chung và vẫn
    còn sau khi restart agent (script chấm restart agent để kiểm tra điều này).
"""
import time

from fastapi import HTTPException, status

from app.config import settings
from app.redis_client import r

WINDOW_SECONDS = 60

# Script Lua: dọn entry cũ → đếm → nếu đầy trả về thời điểm cũ nhất, ngược lại ghi
# entry mới. Chạy atomic trên Redis để nhiều worker không "lọt" quá giới hạn.
_SLIDING_WINDOW = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local member = ARGV[4]
redis.call('ZREMRANGEBYSCORE', key, 0, now - window)
local count = redis.call('ZCARD', key)
if count >= limit then
  local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
  return {1, oldest[2]}
end
redis.call('ZADD', key, now, member)
redis.call('EXPIRE', key, window)
return {0, tostring(count + 1)}
"""

_script = r.register_script(_SLIDING_WINDOW)


def check_rate_limit(key: str) -> None:
    """Raise 429 nếu `key` vượt giới hạn trong 60 giây qua."""
    now = time.time()
    limit = settings.rate_limit_per_minute
    member = f"{now:.6f}:{id(object())}"
    redis_key = f"ratelimit:{key}"

    limited, info = _script(keys=[redis_key], args=[now, WINDOW_SECONDS, limit, member])

    if int(limited) == 1:
        oldest = float(info)
        retry_after = max(1, int(oldest + WINDOW_SECONDS - now) + 1)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "Rate limit exceeded",
                "limit": limit,
                "window_seconds": WINDOW_SECONDS,
                "retry_after_seconds": retry_after,
            },
            headers={
                "Retry-After": str(retry_after),
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": "0",
            },
        )
