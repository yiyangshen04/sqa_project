# Refactor Log

按作业 §4 "call out every refactor in your write-up and explain why you made it" 的要求，集中讲四项重构。每项重构的目的都是**让代码更好测**，不是单纯改风格。

四项都做在做 Q3 单测之前，相当于先把"测试不友好"的接缝改掉，再写测试。

## R1：拆 `Poll.get_result_dict`，注入 RNG

**触发理由**：原 `get_result_dict` 一个方法干三件事——算每个 choice 的票数百分比、随机配 Bootstrap 颜色 class、内部 hardcode 颜色名 list。其中 `secrets.choice` 不可注入，导致 `alert_class` 字段在测试里完全不可预期，断言写不出。

**改动文件**：
- 新增 `polls/services.py`：`compute_poll_results(poll)`、`attach_alert_classes(results, rng=None)`、`build_poll_result_dicts(poll, rng=None)`
- 修改 `polls/models.py`：`Poll.get_result_dict` 变成 1 行 wrapper，删 `import secrets`

**对应作业题**：
- Q3 — `compute_poll_results` 配 FakePoll fake，`attach_alert_classes` 配 StubRNG stub，两个独立单测拿下两种 double 类型
- Q8 — Smell #2 "Long Method / Multiple Responsibilities" 的对照样本

## R3：`poll_vote` 三 bug 一起修 + `Vote` 数据库唯一约束

**触发理由**：
- `poll_vote` view 里 `Choice.objects.get(id=choice_id)` 不存在时直接 500（应该 404）
- 末尾一行 `return render(...)` 永远到不了（前面 if/else 已经覆盖所有分支），是死代码
- `print(vote)` 是调试残留
- 业务规则"一人一票"只在 `user_can_vote()` 应用层挡，**数据库没有 unique 约束**，并发 / 数据迁移 / 管理后台都能绕过

**改动文件**：
- `polls/views.py`：`Choice.objects.get` → `get_object_or_404`，删 unreachable return，删 `print(vote)`，顺手把 4 处 `if form.is_valid:`（漏括号 bug）改成 `if form.is_valid():`
- `polls/models.py`：`Vote.Meta.constraints` 加 `UniqueConstraint(fields=['user', 'poll'], name='one_vote_per_user_per_poll')`
- 新增 `polls/migrations/0003_vote_unique_user_poll.py`

**对应作业题**：
- Q1 — `print(vote)` 和 unreachable return 都是 lint 候选发现（不过最终 Q1 选了其它 5 个更典型的）
- Q7 — 集成测试 `test_second_vote_attempt_blocked_and_db_rejects_raw_duplicate` 同时验证 view 层 + DB 层两道关卡都生效

## R4：抽 `MESSAGE_*_TAGS` 公共常量

**触发理由**：`'alert alert-success alert-dismissible fade show'` 这串字符串在 `polls/views.py` 和 `accounts/views.py` 一字不差复制了 14 次。改一处要找 14 处，测试里也只能用整串字符串字面量去断言。

**改动文件**：
- 新增 `pollme/messages.py`：`SUCCESS_TAGS` / `WARNING_TAGS`
- 修改 `polls/views.py` 和 `accounts/views.py`：8 + 6 处 inline 字符串换成 `extra_tags=SUCCESS_TAGS` / `WARNING_TAGS`

**对应作业题**：
- Q8 — Smell #1 "Duplicated Code" 的教科书例子

## R6：注册校验从 view 搬进 `UserRegistrationForm`

**触发理由**：原 `create_user` view 里有 37 行的"校验代码混在 HTTP 编排里"，三个 flag 变量 `check1/check2/check3` 缓存校验结果再合并判断。这本该是 form 类自己干的事。结果是 view 长，form 几乎空壳，写单测要测校验逻辑只能搭 HTTP request，form 自己测试不出来。

**改动文件**：
- 改 `accounts/forms.py`：`UserRegistrationForm` 添 `clean_username` / `clean_email` / `clean` / `save` 方法
- 改 `accounts/views.py`：`create_user` 从 37 行瘦身到 12 行，删 `from django.contrib.auth.models import User` 直接引用，改用 `get_user_model()` 在 form 内部解析

**对应作业题**：
- Q3 — `clean_username` 可以用 mock patch `User.objects.filter`，单测 ValidationError 触发
- Q7 — `test_form_creates_user_row_and_rejects_duplicate_username` 集成测 form↔User 表
- Q8 — Smell #3 "Feature Envy" 的对照

## 四项总结

| ID | 改动行数（估） | 直接服务的作业题 |
|---|---|---|
| R1 | 约 +50 / -20（services.py 新 + models.py 改） | Q3 fake + stub, Q8 #2 |
| R3 | 约 +20 / -10 | Q7 view↔DB, Q1 候选 |
| R4 | 约 +10 / -14（共 14 处去重） | Q8 #1 |
| R6 | 约 +35 / -25 | Q3 mock, Q7 form↔table, Q8 #3 |

四项都是"为了测试做的"，不是为了清理代码做的。没动核心业务逻辑（投票流程、注册流程、poll CRUD），只调整了**接缝**（seam）让外部能以"注入依赖 / patch 类属性 / 断言行为"的方式介入。

## 故意没做的重构

最初列了 R2（拆 polls_list 排序逻辑）、R5（PollAddForm 创建 choices 用循环）、R7（user_can_vote 用 vote_repository 注入）、R8（get_vote_count @property 改方法），但都没做。理由：
- R2 / R5：纯结构性优化，不为测试服务，且会让单测/集成测试边界更难划清
- R7：现有 mock + spy 两种方式已经够覆盖了，再加一层 repository 抽象反而增加测试负担
- R8：性能问题（N+1 query），属于 Q4 性能测试 interpretation 的内容，不是测试可写性问题

够用就停。
