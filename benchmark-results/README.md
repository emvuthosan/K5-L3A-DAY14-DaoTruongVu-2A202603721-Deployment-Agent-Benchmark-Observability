# Benchmark results (Locust CSV)

CSV của Locust headless từ Part 7 Phần 5 (scaling, cần Docker). Chạy:

```bash
cd 06-lab-complete/benchmark-observability/production
docker compose up -d --scale agent=1
docker compose run --rm locust -f /mnt/locust/locustfile.py --host http://nginx \
  --headless -u 100 -r 10 -t 2m --csv /mnt/results/scale_1
docker compose up -d --scale agent=3
docker compose run --rm locust -f /mnt/locust/locustfile.py --host http://nginx \
  --headless -u 100 -r 10 -t 2m --csv /mnt/results/scale_3
```

Kết quả sẽ sinh ra:
- `scale_1_stats.csv`
- `scale_3_stats.csv`

Điền số từ các file này vào mục 5 của `BENCHMARK_REPORT.md`.
