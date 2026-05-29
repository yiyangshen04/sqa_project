# Q4 Performance Testing

工具用 k6（JS 脚本，CLI 输出干净，CI 友好）。两份脚本都在 [`performance/`](../performance/) 下：

- [`load.js`](../performance/load.js) — sustained 50 VU × 30 秒
- [`stress.js`](../performance/stress.js) — ramping VU 1→50→100→200→0

目标端点：`GET /polls/1/`（poll_detail，无 `@login_required`，内部 `choice_set.count()` + 每个 choice 都查一次 vote_set，是天然的 N+1 嫌疑路径）。Seed 一个 id=1 的 poll，含 3 个 choice。

## 跑法

```
# 1) seed (一次性)
python manage.py shell < seed_perf.py

# 2) start dev server
python manage.py runserver 127.0.0.1:8000 --noreload &

# 3) run scripts
k6 run --summary-export reports/q4_load_summary.json performance/load.js
k6 run --summary-export reports/q4_stress_summary.json performance/stress.js
```

---

## 1. Load Test — sustained 50 VU

**配置**：

| 项 | 值 |
|---|---|
| VU 数 | 50（恒定） |
| Ramp-up | 无（瞬时拉到 50） |
| Duration | 30 秒 |
| Target | `GET /polls/1/` |
| Sleep | 每次请求后 0.5s |
| Threshold | `p(95)<500ms`, `p(99)<1000ms`, `failure rate<1%` |

**结果**：

| 指标 | 值 |
|---|---|
| 请求总数 | 2848 |
| 吞吐量 | 93.4 req/s |
| 平均响应时间 | 27.51 ms |
| 中位数 | 18.86 ms |
| p(90) | 63.72 ms |
| p(95) | 70.84 ms |
| p(99) | 84.71 ms |
| max | 151.02 ms |
| 错误率 | 0.00% (0 of 2848) |
| 所有 threshold | ✓ 全过 |

**响应时间分布图**：

![load 图](../screenshots/q4_load_graph.png)

**k6 终端输出截图**：

![load 终端](../screenshots/q4_load_run.png)

JSON 报告：[`reports/q4_load_summary.json`](q4_load_summary.json)，文本：[`reports/q4_load_output.txt`](q4_load_output.txt)。

**解读**：

50 VU 是这个 dev server 的舒适区。p95 71ms 离 500ms 阈值差近一个数量级，p99 85ms 离 1000ms 阈值差一个数量级以上，说明 baseline 容量充足。p99 只比 p95 高 14ms，说明 long tail 不夸张（max 也只到 151ms）。0 错误。

---

## 2. Stress Test — ramping 1→200 VU

**配置**：

| 项 | 值 |
|---|---|
| 起始 VU | 1 |
| Stages | 15s 升到 50 → 15s 升到 100 → 15s 升到 200 → 15s 降到 0 |
| 总时长 | 60 秒 |
| Target | `GET /polls/1/` |
| Sleep | 每次请求后 0.2s |
| Threshold | `p(95)<2000ms`, `p(99)<5000ms`, `failure rate<5%` |

**结果**：

| 指标 | 值 |
|---|---|
| 请求总数 | 21,486 |
| 吞吐量 | 357.6 req/s |
| 平均响应时间 | 44.82 ms |
| 中位数 | 25.57 ms |
| p(90) | 108.84 ms |
| p(95) | 126.95 ms |
| p(99) | 222.49 ms |
| max | 661.34 ms |
| 峰值 VU | 199 |
| 错误率 | 0.00% (0 of 21486) |
| 所有 threshold | ✓ 全过 |

**响应时间分布图**：

![stress 图](../screenshots/q4_stress_graph.png)

**k6 终端输出截图**：

![stress 终端](../screenshots/q4_stress_run.png)

JSON 报告：[`reports/q4_stress_summary.json`](q4_stress_summary.json)，文本：[`reports/q4_stress_output.txt`](q4_stress_output.txt)。

**解读**：

吞吐从 load 的 93 req/s 飚到 358 req/s（3.8x），但是延迟跟着涨：

| 指标 | load (50 VU) | stress (200 VU 峰值) | 倍数 |
|---|---|---|---|
| avg | 27.51 ms | 44.82 ms | **1.6x** |
| p95 | 70.84 ms | 126.95 ms | **1.8x** |
| p99 | 84.71 ms | 222.49 ms | **2.6x** |
| max | 151.02 ms | 661.34 ms | **4.4x** |

avg / p95 涨幅有限（~1.8x），但 p99 和 max 涨得明显（2.6x / 4.4x），说明压力主要打在 tail latency 上——绝大多数请求还行，少数请求开始排队等。0 错误说明系统没崩，但响应时间分布形状已经变化。

### Where it started to hurt

ramp 到 100 VU 后 max 开始陡升（peak 阶段触到 661ms），p99 翻倍而 p95 涨幅有限——典型的"系统没崩但开始排队"信号。这是单线程 Django dev server 的典型表现：

- `runserver` 是单进程单线程，请求实际排队执行
- 每个 `/polls/1/` 请求会触发：
  - 1 次 `Poll.objects.get(id=1)`
  - 1 次 `poll.choice_set.count()`
  - 模板渲染（中等开销）
- 等于每请求 2 次 DB roundtrip，串行队列下 200 VU 自然堵

### What I'd fix first

按性价比排序：

1. **换 gunicorn / uvicorn**（10 分钟工作量，最大收益）
   `runserver` 上 prod 是 demo-only，换 `gunicorn pollme.wsgi -w 4 --threads 2` 直接把并发上限拉到 4×2=8 worker × thread；吞吐预计提升 3-5 倍

2. **fix `poll_detail` 的 N+1 隐患**（中等工作量）
   现在 `poll.get_result_dict()` 模板 loop 里每个 choice 都触发 `choice.get_vote_count`（一次 COUNT(*) 查询）。改成 `Choice.objects.annotate(num_votes=Count('vote'))` 一次查完，3 choice = 3 query → 1 query，poll detail 数据库时间砍 2/3

3. **加 cache header / template fragment cache**（小工作量）
   poll_detail 在投票期间内容相对稳定（只有 vote count 会变），可以 cache 整页 5 秒或者 fragment cache choice 列表。peak load 下命中 cache 就直接绕过 DB

如果都做了再压一遍，p95 应该能压回到接近 baseline 的水平。

---

## 没做的事

- **没用 spike / soak / scalability 这三种** —— 作业要求 5 选 2，选了 load + stress 已经够展示两种典型 pattern
- **没画时间轴折线图** —— matplotlib 柱状图展示了各百分位的响应时间分布，但没画"响应时间 vs 时间"这种时序图。要做时序图需要 `--out json=raw.json` 拿到每个采样点，复杂度高于本作业范围
- **没并发用户脚本** —— 没有测 vote POST（要 CSRF + session cookie，复杂度上升一档），如果要加可以参考 k6 docs 的 cookie jar 模式
