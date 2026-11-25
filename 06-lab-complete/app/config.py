"""
Config — 12-Factor: mọi cấu hình đọc từ biến môi trường.

Tiêu chí 9 — Config từ environment variables:
  • Mọi giá trị đọc từ os.getenv, có default hợp lý khi chạy local.
  • Không hard-code secret (API key thật, mật khẩu...) trong code.
  • Các biến này được liệt kê đủ trong .env.example.
"""
import os
from dataclasses import dataclass, field

# Nạp .env khi chạy local (trên cloud dùng biến môi trường của platform).
# Không bắt buộc có python-dotenv — thiếu cũng không sao.
try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv là optional
    pass


def _get_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _get_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


@dataclass
class Settings:
    # Platform (Railway/Render) cấp PORT; mặc định 8000 khi chạy local.
    port: int = field(default_factory=lambda: _get_int("PORT", 8000))
    environment: str = field(default_factory=lambda: os.getenv("ENVIRONMENT", "development"))

    # Secret — chỉ đọc từ env, KHÔNG để giá trị thật trong code.
    agent_api_key: str = field(default_factory=lambda: os.getenv("AGENT_API_KEY", ""))

    # Redis dùng chung cho rate limit + cost guard (stateless).
    redis_url: str = field(
        default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379/0")
    )

    # Rate limit: số request / 60 giây cho mỗi API key.
    rate_limit_per_minute: int = field(
        default_factory=lambda: _get_int("RATE_LIMIT_PER_MINUTE", 10)
    )

    # Cost guard: ngân sách tối đa (USD).
    daily_budget_usd: float = field(
        default_factory=lambda: _get_float("DAILY_BUDGET_USD", 1.0)
    )
    monthly_budget_usd: float = field(
        default_factory=lambda: _get_float("MONTHLY_BUDGET_USD", 30.0)
    )

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in ("production", "prod", "staging")


settings = Settings()
