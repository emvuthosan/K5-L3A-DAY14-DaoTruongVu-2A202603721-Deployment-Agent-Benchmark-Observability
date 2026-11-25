# Benchmark & Observability Report — Day 14

**Họ tên:** Đào Trường Vũ — 2A202603721 (K5 / L3A)
**Ngày chạy:** 2026-11-25
**Môi trường:** Windows 10, Python 3.11.9, mock LLM (offline). Agent develop chạy `python app.py`
(uvicorn **1 process, 1 event loop**, `access_log=False`). Số liệu lấy từ `reports/*.json` kèm theo.

> Phần 1–3 (develop, không cần Docker) đã chạy thật — mọi con số dưới đây khớp với file JSON trong `reports/`.
> Phần 4–5 (production stack: Prometheus/Grafana/Jaeger/Locust) **cần máy có Docker**; mục này ghi
> quy trình + kết quả mong đợi để bạn chạy `docker compose up` rồi dán screenshot/CSV.

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng |
|---|---|---|
| p95 latency `/ask` | < 500 ms | Mức người dùng còn thấy "mượt"; cao hơn base latency (~150–200ms) đủ biên cho jitter |
| Error rate `/ask` | < 2 % | Mock LLM có ~1% lỗi upstream + ~3% slow; ngưỡng 2% cho error budget hợp lý |
| Accuracy golden dataset | ≥ 80 % | Quality gate chặn deploy; v2 phải ≥ 80% và không regression |

---

## 2. Benchmark hiệu năng (`develop/load_test.py`)

### 2.1 Concurrency vs latency (agent v2, 300 request/lần)

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO | File |
|---|---|---|---|---|---|---|---|
| 1 | 4.28 | 200.5 | 239.9 | 1733.1 | 1.67% | ✅ PASS | `reports/load_v2_c1.json` |
| 10 | 39.49 | 194.6 | 448.2 | 1695.4 | 1.67% | ✅ PASS | `reports/load_v2_c10.json` |
| 50 | 98.21 | 212.2 | 521.7 | 1698.6 | 1.67% | ❌ FAIL (p95 > 500) | `reports/load_v2_c50.json` |
| 100 | 47.21 | 683.9 | 4217.1 | 4457.3 | 1.33% | ❌ FAIL | `reports/load_v2_c100.json` |

**Nhận xét — RPS có tăng tuyến tính không?** Không.
- Từ concurrency 1→10 RPS tăng gần tuyến tính (4.3 → 39.5, ~9×) vì event loop còn rảnh, các request chủ yếu đang *chờ* mock LLM (I/O) nên chồng lên nhau tốt.
- 10→50 RPS chỉ còn 39.5 → 98 (~2.5×, không phải 5×): bắt đầu tới trần của **1 process uvicorn** — p95 vượt 500ms.
- 50→100 RPS **tụt** (98 → 47) và p50/p95/p99 tăng vọt: quá nhiều coroutine tranh một event loop, request xếp hàng → latency nổ, throughput giảm. Nút thắt là **single process** (develop chạy 1 worker). Production xử lý bằng nhiều worker + nhiều instance sau load balancer (xem Part 5/Phần 5).

### 2.2 Tail latency (agent v2, concurrency 20, 300 request/lần)

| `MOCK_SLOW_RATE` | avg (ms) | p50 (ms) | p95 (ms) | p99 (ms) | File |
|---|---|---|---|---|---|
| 0 | 204.4 | 189.2 | 431.4 | 494.3 | `reports/load_v2_slow0.json` |
| 0.03 (mặc định) | 235.5 | 200.4 | 465.7 | 1671.7 | `reports/load_v2_slow3.json` |
| 0.1 | 358.3 | 201.5 | 1704.3 | 1733.1 | `reports/load_v2_slow10.json` |

**Nhận xét.** Chỉ số **nhạy nhất với request chậm là p95/p99**, không phải average:
- `p50` gần như **không đổi** (189 → 200 → 201 ms) dù tỉ lệ request chậm tăng từ 0% → 10%.
- `p99` nhảy từ 494 → 1672 → 1733 ms; `p95` từ 431 → 1704 ms khi slow rate lên 0.1.
- `average` chỉ tăng vừa phải (204 → 358) vì bị số đông request nhanh kéo xuống — **đây chính là lý do không đặt SLO theo average**: nó che giấu đúng nhóm người dùng chịu latency tệ nhất.

---

## 3. Benchmark chất lượng (`develop/eval/run_eval.py`, golden dataset 23 câu)

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | 4.3% (1/23) | 91.3% (21/23) | **100.0% (23/23)** |
| Avg tokens / câu | 56.8 | 109.0 | 116.3 |
| Tổng cost (USD) | 0.000400 | 0.000760 | 0.000813 |
| Cost / câu đúng (USD) | 0.00039975 | 0.00003619 | **0.00003536** |
| Quality gate | ❌ FAIL | ✅ PASS | ✅ PASS |

File: `reports/eval_v1.json`, `reports/eval_v2.json`, `reports/eval_v2_fixed.json`.

**Những câu v2 trả lời sai ban đầu và cách sửa (Exercise 7.3):**

| ID | Keyword bị thiếu | Đã sửa gì |
|---|---|---|
| `security-02` | `token`, `hết hạn`, `chữ ký` | Thêm entry KB về **JWT vs API key** (keywords `jwt`, `api key`, `xác thực`) vào `develop/utils/mock_llm.py` |
| `scaling-03` | `cpu`, `memory`, `custom metrics` | Thêm entry KB về **Kubernetes HPA** (keywords `hpa`, `kubernetes`, `autoscal`) |

Sau khi sửa và restart agent v2: eval với `--baseline reports/eval_v2.json` → **2 câu được cải thiện, 0 regression, accuracy 100%, quality gate PASS**. (Đã copy phần sửa sang `production/utils/mock_llm.py` để stack Docker Part 7 cũng đạt 100%.)

**Trade-off v1 vs v2 (RAG):** v2 thêm bước retrieval nên **tốn ~2× token** mỗi câu (56.8 → 116.3) và chậm hơn chút, nhưng accuracy nhảy từ 4.3% → 100%. Chỉ số đáng giá nhất là **cost / câu đúng**: v2 **rẻ hơn ~11 lần** (0.00040 → 0.000035) vì v1 trả lời sai gần hết — "rẻ mà sai" thực ra là đắt.

**Exercise 7.4 — Quality gate chặn merge.** Chạy eval **v1** với baseline là report của v2:
```bash
python eval/run_eval.py --url http://localhost:8001 --baseline reports/eval_v2_fixed.json
# → Câu bị regression: 22 → Quality gate ❌ FAIL → exit code 1
```
Dùng trong GitHub Actions để chặn deploy khi chất lượng tụt:
```yaml
- name: Quality gate (eval)
  run: |
    python 06-lab-complete/benchmark-observability/develop/eval/run_eval.py \
      --url http://localhost:8002 --min-accuracy 1.0 --baseline reports/eval_v2_fixed.json
  # bước fail (exit 1) → job đỏ → PR không merge được
```

---

## 4. Observability stack (production) — *cần Docker*

> Chạy: `cd 06-lab-complete/benchmark-observability/production && docker compose up --build -d`.
> Giữ Locust ~30 user trong lúc quan sát. Dán ảnh vào `screenshots/`.

### 4.1 Screenshot cần nộp
- [ ] `screenshots/grafana-dashboard.png` — Grafana có tải (4 Golden Signals: Traffic, Error rate, p95, In-flight)
- [ ] `screenshots/jaeger-slow-trace.png` — 1 trace chậm (thấy span `chat mock-llm-small` chiếm phần lớn thời gian)
- [ ] `screenshots/jaeger-error-trace.png` — 1 trace lỗi (span có event `exception`)
- [ ] `screenshots/prometheus-alert-firing.png` — trang Alerts có **≥ 2 alert đang firing**

### 4.2 Thí nghiệm "phá hệ thống" (điền sau khi chạy — ghi thời gian từ lúc đổi → firing)

| # | Thay đổi | Alert firing (mong đợi) | Thời gian → firing | Panel phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | `AgentHighErrorRate` | ~1 phút | Error rate |
| B | `MOCK_SLOW_RATE=0.3` | `AgentHighLatencyP95` | ~2 phút | p95/p99 Latency |
| C | `LLM_MODEL=mock-llm-large` | `LLMCostBurnRateHigh` | — | Cost USD/giờ |
| D | `docker pause` 1 instance | `AgentInstanceDown` | — | Instances up |
| E | `AGENT_VERSION=v1` | *(không có)* | — | — |

**Vì sao E không làm alert nào firing?** Lỗi của E là **lỗi chất lượng** (agent trả lời kém hơn), nhưng metric hạ tầng (latency, error rate, cost) vẫn xanh. Giám sát hạ tầng **không bắt được** loại sự cố này → cần **eval định kỳ trên golden dataset** (Phần 3) hoặc giám sát chất lượng (LLM-as-judge, feedback người dùng) chạy song song.

### 4.3 Debug bằng trace (điền từ Jaeger)
- `trace_id`: _..._
- Tổng thời gian: _... ms_
- Span chiếm nhiều thời gian nhất: `chat mock-llm-small` (_... ms, ...%_) — LLM chậm, không phải code agent
- Dòng log JSON tương ứng (`docker compose logs agent | grep <trace_id>`): _dán vào_

---

## 5. Benchmark scaling (production, Locust headless, 100 user, 2 phút) — *cần Docker*

```bash
docker compose up -d --scale agent=1
docker compose run --rm locust -f /mnt/locust/locustfile.py --host http://nginx \
  --headless -u 100 -r 10 -t 2m --csv /mnt/results/scale_1
docker compose up -d --scale agent=3
docker compose run --rm locust -f /mnt/locust/locustfile.py --host http://nginx \
  --headless -u 100 -r 10 -t 2m --csv /mnt/results/scale_3
# CSV → benchmark-results/scale_1_stats.csv, scale_3_stats.csv
```

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | _từ scale_1_stats.csv_ | | | | |
| 3 | _từ scale_3_stats.csv_ | | | | |

**Giải thích (dự kiến).** Scale 1→3 tăng RPS và giảm hàng đợi, nhưng **p95 có thể gần như không đổi** nếu nút thắt là **latency của chính LLM** (mỗi call vẫn ~150–200ms + tail) chứ không phải CPU của agent. Thêm instance giúp *throughput* và *saturation*, không rút ngắn thời gian một LLM call. (Điền số thật từ CSV khi nộp.)

---

## 6. Kết luận

- 3 điều học được:
  1. **p95/p99 mới phản ánh trải nghiệm thật** — average che giấu tail latency (số liệu 2.2 chứng minh: slow rate 0→0.1 làm p99 ×3.5 trong khi p50 gần như đứng yên).
  2. **Chất lượng phải đo riêng bằng eval** — dashboard xanh không có nghĩa agent trả lời đúng (thí nghiệm E); golden dataset + quality gate chặn regression trong CI.
  3. **"Rẻ mà sai" là đắt** — cost/câu đúng của v2 thấp hơn v1 ~11 lần dù v2 tốn token gấp đôi.
- Nếu lên production thật sẽ thêm: alert **p99** và **error budget burn-rate** (multi-window), **synthetic check** từ ngoài (bắt lỗi 504 ở tầng LB mà metric agent không thấy), metric **retrieval hit ratio** và **chất lượng** (tỉ lệ phản hồi bị người dùng down-vote), và **trace sampling** khi traffic lớn.
