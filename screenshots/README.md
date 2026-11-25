# Screenshots

Đặt ảnh chụp màn hình bằng chứng vào thư mục này (cần máy có Docker / sau khi deploy):

**Deployment (Part 3 + Part 6):**
- `deploy-dashboard.png` — dashboard Railway/Render: service agent + Redis "running"
- `health-200.png` — `GET /health` → 200 trên URL public
- `ask-200-401-429.png` — 4 lệnh tự kiểm CP6 (401 / 200 / 429)

**Observability (Part 7, stack Docker):**
- `grafana-dashboard.png` — Grafana có tải (4 Golden Signals)
- `jaeger-slow-trace.png` — 1 trace chậm (span LLM chiếm phần lớn thời gian)
- `jaeger-error-trace.png` — 1 trace lỗi (span có event `exception`)
- `prometheus-alert-firing.png` — trang Alerts có ≥ 2 alert đang **firing**
