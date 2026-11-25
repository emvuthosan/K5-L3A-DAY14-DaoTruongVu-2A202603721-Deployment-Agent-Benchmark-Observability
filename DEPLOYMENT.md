# Deployment Information — Day 14 Final Project (Part 6 agent)

> ⚠️ **Cần sinh viên tự deploy:** việc tạo tài khoản Railway/Render và deploy phải do bạn thực hiện
> (cần đăng nhập + tài khoản cá nhân). File này đã chuẩn bị sẵn mọi lệnh và cấu hình; chỉ cần
> điền **URL public** sau khi deploy xong và dán ảnh vào `screenshots/`.

## Public URL

```
https://<your-agent>.up.railway.app      ← ĐIỀN URL thật sau khi deploy
```

## Platform

Railway (chính) — cấu hình [06-lab-complete/railway.toml](06-lab-complete/railway.toml)
(hoặc Render — [06-lab-complete/render.yaml](06-lab-complete/render.yaml)).

## Các bước deploy (Railway, theo lưu ý K5 — deploy agent Part 6)

```bash
cd 06-lab-complete

# 1) Tạo một Redis service trên Railway (New → Database → Redis), copy REDIS_URL của nó
# 2) Đặt biến môi trường cho service agent (KHÔNG commit secret vào repo):
railway variables set AGENT_API_KEY=<đặt-key-mạnh-ngẫu-nhiên>
railway variables set REDIS_URL=<REDIS_URL-của-Redis-vừa-tạo>
railway variables set ENVIRONMENT=production
railway variables set RATE_LIMIT_PER_MINUTE=10
railway variables set DAILY_BUDGET_USD=1.0 MONTHLY_BUDGET_USD=30.0

# 3) Deploy (Railway đọc railway.toml: builder=DOCKERFILE, healthcheckPath=/health)
railway up
railway domain          # lấy public URL
```

> Railway/Render tự cấp biến `PORT`; Dockerfile đã nghe theo `${PORT:-8000}`.
> Đảm bảo `GET /ready` trả **200** (agent kết nối được Redis) trước khi chụp ảnh.

## Test Commands (CP6 — chạy trên URL public)

```bash
URL=https://<your-agent>.up.railway.app
KEY=<AGENT_API_KEY-của-bạn>

# 1) Health → 200
curl -i $URL/health
# Expected: HTTP/1.1 200 OK   {"status":"ok"}

# 2) Thiếu API key → 401
curl -i -X POST $URL/ask -H "Content-Type: application/json" \
     -d '{"question":"Hello"}'
# Expected: HTTP/1.1 401 Unauthorized

# 3) Có API key → 200
curl -i -X POST $URL/ask -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
     -d '{"question":"What is deployment?"}'
# Expected: HTTP/1.1 200 OK

# 4) Vượt rate limit → 429
for i in $(seq 1 15); do \
  curl -s -o /dev/null -w "%{http_code} " -X POST $URL/ask \
       -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
       -d '{"question":"test"}'; done
# Expected: 200 ... 200 429 429 (kèm header Retry-After)

# (tuỳ chọn) chạy script chấm với URL đã deploy:
#   python check_production_ready.py --public-url $URL
```

## Environment Variables đặt trên nền tảng (không ghi trong code)

- `PORT` — do platform cấp
- `AGENT_API_KEY` — secret
- `REDIS_URL` — trỏ tới Redis service
- `ENVIRONMENT=production`
- `RATE_LIMIT_PER_MINUTE`, `DAILY_BUDGET_USD`, `MONTHLY_BUDGET_USD`

## Screenshots (đặt trong `screenshots/`)

- [ ] `screenshots/deploy-dashboard.png` — dashboard nền tảng (service + Redis "running")
- [ ] `screenshots/health-200.png` — `GET /health` trả 200 trên URL public
- [ ] `screenshots/ask-200-401-429.png` — 4 lệnh tự kiểm CP6
