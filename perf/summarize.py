"""压测结果汇总器：把 locust 导出的 *_stats.csv 摊平成一张可对比的表，并自动算在飞并发数。

为什么要这个脚本：locust 终端输出列太宽、换行后肉眼对齐容易看错行，而且
"在飞并发数 = 吞吐 × 平均响应时间"这个关键指标它不直接给，每次手算容易漏。
汇总器把它一起算出来，跨档对比时直接看 L 那一列就知道压力是不是真打进去了。

运行：& ".venv\Scripts\python.exe" perf\summarize.py            # 扫 log 下所有结果
     & ".venv\Scripts\python.exe" perf\summarize.py login      # 只看文件名含 login 的
"""
import csv
import glob
import os
import sys

PATTERN = sys.argv[1] if len(sys.argv) > 1 else ""


def read_stats(path):
    """读 _stats.csv，取 Aggregated 那一行（整体汇总），返回 dict"""
    with open(path, encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r.get("Name") == "Aggregated"]
    if not rows:
        return None
    r = rows[0]
    reqs = int(float(r["Request Count"]))
    fails = int(float(r["Failure Count"]))
    rps = float(r["Requests/s"])
    avg_ms = float(r["Average Response Time"])
    return {
        "file": os.path.basename(path).replace("_stats.csv", ""),
        "reqs": reqs,
        "fail_pct": fails / reqs * 100 if reqs else 0.0,
        "rps": rps,
        "p50": float(r["50%"]),
        "p95": float(r["95%"]),
        "p99": float(r["99%"]),
        "max": float(r["Max Response Time"]),
        # 利特尔法则：L = λ × W（W 要从毫秒换成秒）
        "lift": rps * avg_ms / 1000,
    }


rows = []
for p in sorted(glob.glob(os.path.join("log", f"perf_*{PATTERN}*_stats.csv"))):
    d = read_stats(p)
    if d:
        rows.append(d)

if not rows:
    print("没找到结果文件，先跑压测并带 --csv 参数")
    sys.exit(1)

head = f"{'档':<22}{'请求数':>8}{'失败%':>7}{'吞吐':>9}{'P50':>7}{'P95':>7}{'P99':>7}{'Max':>8}{'在飞L':>8}"
print(head)
print("-" * len(head))
for d in rows:
    print(f"{d['file']:<22}{d['reqs']:>8}{d['fail_pct']:>7.2f}{d['rps']:>9.2f}"
          f"{d['p50']:>7.0f}{d['p95']:>7.0f}{d['p99']:>7.0f}{d['max']:>8.0f}{d['lift']:>8.1f}")
print("\n单位：耗时 ms，吞吐 req/s。在飞L = 吞吐 × 平均耗时，即同一瞬间系统里正在处理的请求数。")
