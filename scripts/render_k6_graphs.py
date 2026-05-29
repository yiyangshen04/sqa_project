import json
from pathlib import Path

import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
SCREEN = ROOT / "screenshots"

METRICS = ["avg", "med", "p(90)", "p(95)", "p(99)", "max"]
LABELS = ["avg", "median", "p90", "p95", "p99", "max"]


def render(json_path: Path, out_path: Path, title: str, accent: str) -> None:
    with open(json_path) as f:
        data = json.load(f)
    m = data["metrics"]["http_req_duration"]
    values = [m.get(k, 0) for k in METRICS]
    rps = data["metrics"]["http_reqs"].get("rate", 0)
    fail_pct = data["metrics"]["http_req_failed"].get("rate", 0) * 100

    fig, ax = plt.subplots(figsize=(9, 5.2), dpi=120)
    bars = ax.bar(LABELS, values, color=accent, edgecolor="#333", linewidth=0.6)
    ax.set_ylabel("Response time (ms)")
    ax.set_xlabel("Metric")
    ax.set_title(title)
    ax.grid(axis="y", alpha=0.3)
    ax.set_axisbelow(True)
    top = max(values) * 1.18
    ax.set_ylim(0, top)
    for bar, v in zip(bars, values, strict=True):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + top * 0.015,
            f"{v:.1f} ms",
            ha="center",
            fontsize=9,
        )

    fig.text(
        0.99,
        0.01,
        f"throughput = {rps:.1f} req/s    error rate = {fail_pct:.2f}%",
        ha="right",
        fontsize=9,
        color="#666",
    )
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    print(f"wrote {out_path}")


render(
    ROOT / "reports/q4_load_summary.json",
    SCREEN / "q4_load_graph.png",
    "k6 Load Test — sustained 50 VU × 30s on GET /polls/1/",
    "#4a90e2",
)
render(
    ROOT / "reports/q4_stress_summary.json",
    SCREEN / "q4_stress_graph.png",
    "k6 Stress Test — ramping 1→200 VU on GET /polls/1/",
    "#e25c5c",
)
