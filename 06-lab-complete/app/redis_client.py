"""
Kết nối Redis dùng chung cho rate limiter và cost guard.

  • Đọc REDIS_URL từ config.
  • App vẫn KHỞI ĐỘNG ĐƯỢC khi Redis chưa sẵn sàng (không ping lúc import —
    client của redis-py là lazy, chỉ mở kết nối ở lệnh đầu tiên).
  • redis_healthy() dùng cho GET /ready: Redis không kết nối được → False.
"""
import redis

from app.config import settings

# Lazy client — KHÔNG ping ở đây để app còn khởi động được khi Redis chưa lên.
# socket_connect_timeout giữ cho /ready trả 503 nhanh thay vì treo.
r = redis.from_url(
    settings.redis_url,
    decode_responses=True,
    socket_connect_timeout=2,
    socket_timeout=2,
)


def redis_healthy() -> bool:
    """True nếu Redis trả PONG, False nếu không kết nối được."""
    try:
        return bool(r.ping())
    except Exception:
        return False
