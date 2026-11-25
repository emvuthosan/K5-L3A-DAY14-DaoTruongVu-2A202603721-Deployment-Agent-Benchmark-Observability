"""
Cost guard (tiêu chí 8).

  • Cộng dồn chi phí LLM (tính theo token) vào Redis theo ngày.
  • Tổng chi phí vượt DAILY_BUDGET_USD → HTTP 402.
  • State trong Redis → dùng chung giữa các worker / instance.
"""
from datetime import datetime, timezone

from fastapi import HTTPException, status

from app.config import settings
from app.redis_client import r

# Giá USD / 1K tokens (tham khảo gpt-4o-mini)
PRICE_INPUT_PER_1K = 0.00015
PRICE_OUTPUT_PER_1K = 0.0006


def _today_key() -> str:
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"cost:daily:{day}"


def _current_cost() -> float:
    try:
        value = r.get(_today_key())
        return float(value) if value else 0.0
    except Exception:
        return 0.0


def check_budget() -> None:
    """Gọi TRƯỚC khi gọi LLM. Hết budget → raise HTTPException(status_code=402)."""
    budget = settings.daily_budget_usd
    current = _current_cost()
    if current >= budget:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error": "Daily budget exceeded",
                "spent_usd": round(current, 6),
                "budget_usd": budget,
            },
        )


def record_cost(input_tokens: int, output_tokens: int) -> float:
    """Gọi SAU khi gọi LLM. Cộng chi phí request vào tổng ngày, trả về chi phí request."""
    cost = (
        input_tokens / 1000 * PRICE_INPUT_PER_1K
        + output_tokens / 1000 * PRICE_OUTPUT_PER_1K
    )
    try:
        key = _today_key()
        r.incrbyfloat(key, cost)
        # Giữ 2 ngày rồi tự hết hạn (dọn key cũ).
        r.expire(key, 60 * 60 * 48)
    except Exception:
        pass
    return cost
