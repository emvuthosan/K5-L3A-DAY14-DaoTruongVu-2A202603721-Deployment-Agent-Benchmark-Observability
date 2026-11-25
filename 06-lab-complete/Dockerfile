# ============================================================
# Multi-stage production Dockerfile (tiêu chí 1)
#   • Stage builder: cài dependencies vào venv
#   • Stage runtime: base slim, chỉ copy venv + source, chạy non-root
#   • HEALTHCHECK gọi GET /health
#   • CMD lắng nghe theo biến PORT (mặc định 8000), uvicorn là PID 1 (exec)
# ============================================================

# ---------- Stage 1: builder ----------
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app
RUN python -m venv "$VIRTUAL_ENV"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---------- Stage 2: runtime ----------
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PORT=8000

WORKDIR /app

# Chỉ copy môi trường đã cài sẵn từ builder → image gọn, không có toolchain build
COPY --from=builder /opt/venv /opt/venv

# Copy source
COPY app ./app
COPY utils ./utils

# User non-root
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Liveness: gọi /health theo đúng PORT
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import os,urllib.request,sys; \
url='http://127.0.0.1:%s/health' % os.getenv('PORT','8000'); \
sys.exit(0 if urllib.request.urlopen(url, timeout=2).status==200 else 1)"

# exec uvicorn → uvicorn là PID 1 (nhận SIGTERM khi `docker stop`)
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2"]
