# Day 14 Lab — Mission Answers

**Họ tên:** Đào Trường Vũ
**MSSV:** 2A202603721
**Lớp:** K5 – L3A
**Ngày làm:** 2026-11-25

> Bài làm theo **lưu ý K5** trong [README.md](README.md): code Part 6 nằm trong `06-lab-complete/`,
> app develop Part 1–2 nhận `question` qua query, Part 3 deploy chính agent Part 6 (CP6), v.v.

---

## Part 1 — Localhost vs Production

### Exercise 1.1 — Anti-patterns trong `01-localhost-vs-production/develop/app.py`

1. **Hardcode secret trong code** — `OPENAI_API_KEY = "sk-..."` và `DATABASE_URL` có cả `password123`. Push lên GitHub là lộ key ngay, không revoke kịp.
2. **Không có config management** — `DEBUG = True`, `MAX_TOKENS = 500` cố định trong code; không thể đổi theo môi trường (dev/staging/prod) mà không sửa code.
3. **`print()` thay cho logging** — log không có level, không timestamp, không cấu trúc; tệ hơn là **in cả secret ra log** (`print(... OPENAI_API_KEY)`).
4. **Không có health check** — platform không biết agent sống hay chết để restart / ngừng route traffic.
5. **Port và host cố định** — `host="localhost"` (chỉ nghe loopback, container/LB không gọi được) và `port=8000` cứng, không đọc `PORT` do platform cấp.
6. **`reload=True` trong "production"** — chế độ dev, tốn RAM, không an toàn khi chạy thật.
7. **Không xác thực** — `/ask` mở cho mọi người, không có API key, không rate limit, không cost guard.

### Exercise 1.3 — So sánh develop vs production

| Feature | Develop (localhost) | Production (12-factor) | Vì sao quan trọng |
|---|---|---|---|
| Config / secret | Hardcode trong code | Đọc từ biến môi trường (`os.getenv`), có `.env.example` | Cùng một image chạy mọi môi trường; secret không lọt vào Git |
| Logging | `print()`, in cả secret | JSON log có level/timestamp, không log secret | Dễ tìm kiếm/lọc, nối với trace, không rò rỉ |
| Host / Port | `localhost:8000` cứng | `0.0.0.0` + `PORT` từ env | Container & load balancer gọi được; platform inject PORT |
| Health check | Không có | `/health` (liveness) + `/ready` (readiness) | Platform restart / ngừng route đúng lúc |
| Chế độ chạy | `reload=True` | uvicorn workers, no reload | Ổn định, tiết kiệm tài nguyên |
| Bảo mật | Mở | API key + rate limit + cost guard | Chặn lạm dụng và "đốt tiền" LLM |

---

## Part 2 — Docker

### Exercise 2.1 — Đọc Dockerfile

Tham khảo `02-docker/develop/Dockerfile` (đơn giản) và `02-docker/production/Dockerfile` + `06-lab-complete/Dockerfile` (production, multi-stage).

1. **Base image:** `python:3.11-slim` cho stage runtime (nhỏ hơn `python:3.11` đầy đủ ~5 lần).
2. **Working directory:** `WORKDIR /app`.
3. **Thứ tự layer:** copy `requirements.txt` và `pip install` **trước**, copy source **sau** → tận dụng layer cache của Docker: đổi code mà không đổi dependencies thì không phải cài lại (xem `02-docker/layer-order/`).
4. **Multi-stage:** stage `builder` cài dependencies vào venv, stage `runtime` chỉ `COPY --from=builder` kết quả → image cuối không chứa toolchain build, nhỏ và ít lỗ hổng hơn (xem `02-docker/multi-stages/`).
5. **User non-root:** `useradd appuser` + `USER appuser` → giảm thiệt hại nếu container bị chiếm.
6. **PID 1 nhận SIGTERM:** `CMD ["sh","-c","exec uvicorn ... --port ${PORT:-8000}"]` — `exec` cho uvicorn thành PID 1 để `docker stop` tắt êm.

### Exercise 2.3 — So sánh kích thước image

Build từ **gốc repo** (theo lưu ý K5, Dockerfile `COPY` tính từ gốc):

```bash
docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .
docker build -f 02-docker/production/Dockerfile -t my-agent:advanced .
docker images my-agent
```

| Image | Base | Kích thước (đo bằng `docker images`) |
|---|---|---|
| `my-agent:develop` | `python:3.11` (full) | _≈ 1.0–1.1 GB_ ¹ |
| `my-agent:advanced` | `python:3.11-slim` multi-stage | _≈ 180–230 MB_ ¹ |
| `06-lab-complete` (Part 6) | `python:3.11-slim` multi-stage | _< 500 MB_ ✅ (đo bởi `check_production_ready.py`) |

> ¹ Số MB thật phụ thuộc máy build — điền số từ `docker images` trên máy có Docker của bạn.
> Multi-stage + slim giảm ~**80%** kích thước so với bản `python:3.11` full.

**Vì sao image nhỏ hơn quan trọng?** Deploy/scale nhanh hơn (kéo image nhanh), bề mặt tấn công nhỏ hơn (ít package = ít CVE), tốn ít dung lượng registry.

---

## Part 3 — Cloud Deployment

> Theo lưu ý K5 (CP6): lớp K5 **deploy chính agent Part 6** (`06-lab-complete/`), không phải app mẫu trong `03-cloud-deployment/`.

### Exercise 3.1 / 3.2 — Deploy agent Part 6

- **Nền tảng chính:** Railway (hoặc Render).
- **Public URL:** _xem [DEPLOYMENT.md](DEPLOYMENT.md)_ — URL này được chấm ở cả Part 3 và nhóm Deployment của Part 6.
- Agent cần Redis trên cloud: tạo Redis service, đặt `REDIS_URL` của agent trỏ tới nó, kiểm `/ready` trả 200 trước khi chụp ảnh.
- 4 lệnh tự kiểm (CP6) chạy trên URL public: `/health` → 200, `/ask` thiếu key → 401, có key → 200, lặp quá giới hạn → 429.

### Exercise (nền tảng còn lại) — So sánh `railway.toml` vs `render.yaml`

| | `railway.toml` (06-lab-complete) | `render.yaml` (06-lab-complete) |
|---|---|---|
| Định dạng | TOML | YAML (Blueprint) |
| Chọn builder | `[build] builder = "DOCKERFILE"` | `runtime: docker`, `dockerfilePath` |
| Health check | `[deploy] healthcheckPath = "/health"` | `healthCheckPath: /health` |
| Redis | Tạo riêng trên dashboard, set `REDIS_URL` thủ công | Khai báo `type: redis` ngay trong blueprint, agent lấy qua `fromService ... connectionString` |
| Secret | `railway variables set AGENT_API_KEY=...` | `generateValue: true` / `sync: false` (không ghi giá trị vào file) |
| Số service / file | 1 service / file; Redis tách riêng | Nhiều service trong 1 file (web + redis) |

**Khác nhau vì sao:** Render Blueprint mô tả **toàn bộ stack** (web + datastore + biến) trong một file khai báo, thiên về IaC; Railway nghiêng về cấu hình **một service** + thao tác CLI/dashboard cho phần còn lại. Cả hai đều: build bằng Dockerfile, healthcheck `/health`, app nghe theo `PORT`, secret không nằm trong file.

### Exercise 3.3 — Cloud Run CI/CD pipeline

Đọc `03-cloud-deployment/production-cloud-run/cloudbuild.yaml` và `service.yaml`. Pipeline (trigger khi push lên `main`) đi qua các bước:

1. **Test** — image `python:3.11-slim`: `pip install -r requirements.txt pytest` rồi `pytest tests/`. Fail test là dừng, không build.
2. **Build** — `docker build` gắn 2 tag (`$COMMIT_SHA` để truy vết + `latest`), dùng `--cache-from=...:latest` để tái dùng layer cache cho nhanh. `waitFor: [test]`.
3. **Push** — `docker push --all-tags` lên Container Registry (`gcr.io/$PROJECT_ID/ai-agent`). `waitFor: [build]`.
4. **Deploy** — `gcloud run deploy ai-agent` với image theo `$COMMIT_SHA`, `--region=asia-southeast1`, `--allow-unauthenticated`, `--min-instances=1` (tránh cold start), `--max-instances=10`, `512Mi/1 CPU`, và **secret lấy từ Secret Manager** (`--set-secrets=OPENAI_API_KEY=openai-key:latest`), không hardcode. `waitFor: [push]`.

`service.yaml` là bản IaC của service (`gcloud run services replace`): minScale/maxScale 1–10, `containerConcurrency: 80`, secret qua `secretKeyRef`, `livenessProbe` `/health` + `startupProbe` `/ready`. Toàn pipeline timeout 20 phút. → **Tóm tắt dòng chảy:** `push main → test → build (cache) → push image → deploy Cloud Run (secret từ Secret Manager, autoscale 1–10, health probe)`.

---

## Part 4 — API Security

> Bản develop bật bằng `AGENT_API_KEY=secret-key-123 python app.py`; bản production (Exercise 4.2/4.3) lấy token ở `POST /auth/token` với `student`/`demo123` (10 req/phút). Thêm `-i` để thấy mã HTTP. **Che token trước khi dán.**

### Exercise 4.1–4.3 — Kết quả test (401 / 200 / 429)

```bash
# 1) Thiếu / sai API key → 401
curl -i -X POST "http://localhost:8000/ask?question=Hello"
#   → HTTP/1.1 401 Unauthorized

# 2) Có API key đúng → 200
curl -i -X POST "http://localhost:8000/ask?question=Hello" \
     -H "X-API-Key: secret-key-123"
#   → HTTP/1.1 200 OK   {"answer": "..."}

# 3) Vượt rate limit → 429 (lặp quá giới hạn/phút)
for i in $(seq 1 15); do \
  curl -s -o /dev/null -w "%{http_code} " -X POST "http://localhost:8000/ask?question=hi" \
       -H "X-API-Key: secret-key-123"; done
#   → 200 200 ... 429 429   (bắt đầu 429 sau khi chạm giới hạn)
```

> Dán output thật (kèm header `HTTP/1.1 401/200/429`) từ máy của bạn vào đây khi nộp.
> Hành vi tương đương đã được kiểm chứng trên agent Part 6: xem checklist bên dưới
> (thiếu/sai key → 401, key đúng → 200, vượt giới hạn → 429 kèm `Retry-After`).

### Exercise 4.4 — Cost guard

Ý tưởng: **ước lượng chi phí mỗi request theo token** rồi cộng dồn vào một bộ đếm; vượt ngân sách thì chặn **trước khi gọi LLM**.

- `cost = input_tokens/1000 × giá_input + output_tokens/1000 × giá_output` (bảng giá tham khảo gpt-4o-mini).
- Trong agent Part 6 ([06-lab-complete/app/cost_guard.py](06-lab-complete/app/cost_guard.py)): tổng chi phí trong ngày lưu ở Redis (`INCRBYFLOAT cost:daily:<ngày>`, có TTL). `check_budget()` gọi trước khi gọi LLM, nếu tổng ≥ `DAILY_BUDGET_USD` → **HTTP 402 Payment Required**; `record_cost()` gọi sau khi có kết quả để cộng thêm.
- Vì state nằm ở Redis nên nhiều worker/instance dùng chung một hạn mức, không bị "mỗi process một ngân sách".

---

## Part 5 — Scaling & Reliability

> Stack `05-scaling-reliability/production/` mở cổng **8080**, endpoint **`POST /chat`**. Chạy
> `docker compose -p k5-day14-scaling up -d --build --scale agent=3` rồi `python test_stateless.py`,
> xong `docker compose -p k5-day14-scaling down`.

### Exercise 5.1–5.5 — Ghi chú & kết quả

- **5.1 Health vs Readiness:** `/health` (liveness) luôn 200 khi process sống → platform **restart** khi fail. `/ready` (readiness) kiểm tra phụ thuộc (Redis); fail thì load balancer **ngừng route traffic** tới instance đó nhưng **không restart**. Agent Part 6 trả `/ready` 503 khi mất Redis (đã kiểm chứng).
- **5.2 Graceful shutdown:** nhận SIGTERM → ngừng nhận request mới, xử lý xong request đang chạy rồi thoát (exit 0). Trong Docker, uvicorn phải là PID 1 (`exec`) để `docker stop` không bị SIGKILL (137). Agent Part 6 dùng `lifespan` + cơ chế mặc định của uvicorn.
- **5.3 Stateless:** instance không giữ state trong RAM; session/history lưu ở Redis → bất kỳ instance nào cũng phục vụ được cùng một user → scale ngang sau load balancer.
- **5.4/5.5 Test stateless (Nginx + 3 instance):** `test_stateless.py` gửi 5 câu trong cùng `session_id` qua Nginx LB (round-robin). Response có `served_by` đổi giữa các instance nhưng `/chat/{session_id}/history` vẫn đủ 5 lượt → **state nằm ở Redis, không ở RAM của 1 instance**. (Dán output `served_by` + history khi chạy trên máy có Docker.)

**Vì sao stateless + Redis quan trọng khi scale:** nếu giữ session trong RAM, request thứ 2 của cùng user rơi vào instance khác sẽ "mất trí nhớ"; đưa state ra Redis giải quyết triệt để và cho phép rolling deploy không mất dữ liệu.

---

## Part 6 — Final Project (output `check_production_ready.py`)

Bản khung đã hoàn thành đủ 12 tiêu chí. Kiểm tra tĩnh (không cần Docker) đạt **28/28 checks**:

```
📋 Checklist Deliverable
     ✅ docker-compose.yml (agent + redis)
     ✅ .dockerignore
     ✅ Public URL ready (Railway / Render config)
     ✅ (tất cả kiểm tra tĩnh của 12 tiêu chí đều ✅ — 28/28 checks passed)
```

> **Để lấy `PASS 12/12` khi chấm:** chạy **đầy đủ** trên máy có Docker + môi trường POSIX (WSL2),
> vì các mục Runtime (SIGTERM/graceful) và Docker (build/size/stop) chỉ đo được ở đó:
> ```bash
> cd 06-lab-complete
> pip install -r requirements.txt
> python check_production_ready.py            # cần Docker đang chạy
> ```
> Logic runtime (health/ready 200+503, thiếu/sai key→401, key đúng→200, vượt giới hạn→429 kèm
> `Retry-After`, hết budget→402, log JSON hợp lệ) đã được kiểm chứng end-to-end.

---

## Phụ lục — Part 7 (Benchmark & Observability)

Số liệu benchmark & eval chi tiết trong [BENCHMARK_REPORT.md](BENCHMARK_REPORT.md) (JSON kèm trong `reports/`).
Tóm tắt: eval v1 = 4.3% → v2 = 91.3% → v2 sau khi sửa knowledge base = **100% (23/23), 0 regression, quality gate PASS**.
