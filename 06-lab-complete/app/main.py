"""
Production AI Agent — Part 6 Final Project

Kết hợp mọi thứ đã học ở Part 1–5:
  • /health (liveness)      — tiêu chí 4
  • /ready  (readiness)     — tiêu chí 5, 503 khi mất Redis
  • API key (X-API-Key)     — tiêu chí 6, thiếu/sai → 401
  • Rate limit (Redis)      — tiêu chí 7, vượt → 429
  • Cost guard (Redis)      — tiêu chí 8, hết budget → 402
  • Config từ env           — tiêu chí 9
  • Structured JSON logging — tiêu chí 10
  • Graceful shutdown       — tiêu chí 11 (lifespan + uvicorn mặc định)

Chạy: uvicorn app.main:app --workers 2
"""
import json
import logging
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.auth import verify_api_key
from app.config import settings
from app.cost_guard import check_budget, record_cost
from app.rate_limiter import check_rate_limit
from app.redis_client import redis_healthy
from utils.mock_llm import ask as llm_ask


# ──────────────────────────────────────────────────────────
# Tiêu chí 10 — Structured logging: mỗi dòng log là 1 JSON object
# ──────────────────────────────────────────────────────────
class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "lvl": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        # Trường bổ sung truyền qua logger.info(..., extra={"extra": {...}})
        extra = getattr(record, "extra", None)
        if isinstance(extra, dict):
            payload.update(extra)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def _configure_logging() -> logging.Logger:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    return logging.getLogger("agent")


logger = _configure_logging()


def _log(event: str, **fields):
    logger.info(event, extra={"extra": fields})


# ──────────────────────────────────────────────────────────
# Lifespan — tiêu chí 11: dọn dẹp khi tắt (SIGTERM dùng cơ chế mặc định
# của uvicorn: ngừng nhận request mới, xử lý xong request đang chạy rồi thoát)
# ──────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    _log("startup", environment=settings.environment, port=settings.port)
    yield
    _log("shutdown", reason="SIGTERM / graceful")


app = FastAPI(title="Production AI Agent", version="1.0.0", lifespan=lifespan)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    user_id: str | None = None


def _estimate_tokens(text: str) -> int:
    # Ước lượng thô ~4 ký tự / token.
    return max(1, len(text) // 4)


# ──────────────────────────────────────────────────────────
# Health / Readiness
# ──────────────────────────────────────────────────────────
@app.get("/health")
def health():
    """Liveness: luôn 200 khi process còn chạy (kể cả khi Redis chưa kết nối)."""
    return {"status": "ok"}


@app.get("/ready")
def ready():
    """Readiness: 200 khi sẵn sàng, 503 khi Redis không kết nối được."""
    if not redis_healthy():
        raise HTTPException(status_code=503, detail="Redis not available")
    return {"ready": True}


# ──────────────────────────────────────────────────────────
# Endpoint chính
# ──────────────────────────────────────────────────────────
@app.post("/ask")
def ask(body: AskRequest, api_key: str = Depends(verify_api_key)):
    started = time.perf_counter()

    # Tiêu chí 7: rate limit theo API key → 429
    check_rate_limit(api_key)

    # Tiêu chí 8: chặn trước khi tốn tiền → 402
    check_budget()

    answer = llm_ask(body.question)

    # Ghi nhận chi phí sau khi gọi LLM
    cost = record_cost(_estimate_tokens(body.question), _estimate_tokens(answer))

    elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
    _log("request", path="/ask", status=200, ms=elapsed_ms, cost_usd=round(cost, 6))
    return {"question": body.question, "answer": answer}


# ──────────────────────────────────────────────────────────
# Xử lý lỗi: không lộ stack trace, trả JSON gọn
# ──────────────────────────────────────────────────────────
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    _log("error", path=str(request.url.path), error=type(exc).__name__)
    return JSONResponse(status_code=500, content={"error": "Internal server error"})
