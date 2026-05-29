---
title: "Software Quality Assurance Project Report — Django Poll App"
author: "Name: __________    Student ID: __________"
date: "May 2026"
---

# Introduction

For this project I applied a full set of quality-assurance work to the open-source [Django Poll App](https://github.com/devmahmud/Django-Poll-App), a Python/Django web application that lets users create polls, vote, and view results. The work covers static analysis, unit tests, integration tests, UI automation, and performance tests, all wired together into a CI/CD pipeline on GitHub Actions.

I did not rewrite the application from scratch. Instead I worked on the real upstream code and applied QA techniques to it. Before writing any tests I made four small refactors to remove a few seams that were hostile to testing, which is what made the later unit and integration tests possible. I explain each refactor below.

The report is organised question by question (Q1 through Q9). Wherever a command, configuration, or result is involved, I have attached a screenshot.

# Refactoring Notes

The project brief asks me to call out every change I made to the source code, so I describe the four refactors here up front. All of them were done before writing tests, all of them aim to make the code easier to test, and none of them touch the core business logic (the voting flow, the registration flow, poll CRUD). They only adjust the "seams" so that tests can intervene through dependency injection, patching class attributes, or asserting behaviour.

| ID | What changed | Files | Question served |
|---|---|---|---|
| R1 | Split `Poll.get_result_dict` into `compute_poll_results` (pure calculation) and `attach_alert_classes` (colouring, with an injectable random source); the original method became a one-line wrapper; removed `import secrets` | new `polls/services.py`, edited `polls/models.py` | Q3 (fake + stub), Q8 #2 |
| R3 | Fixed three bugs in `poll_vote` at once and added a database unique constraint on `Vote` | edited `polls/views.py`, `polls/models.py`, new `polls/migrations/0003_vote_unique_user_poll.py` | Q7 (view↔DB), Q1 |
| R4 | Extracted an alert-class string that had been copied 14 times into shared constants | new `pollme/messages.py`, edited two views | Q8 #1 |
| R6 | Moved registration validation out of a 37-line view into the form's `clean_*` and `save()`, trimming the view to 12 lines | edited `accounts/forms.py`, `accounts/views.py` | Q3 (mock), Q7 (form↔table), Q8 #3 |

The three bugs R3 fixed: `Choice.objects.get(id=...)` raised a 500 when the object did not exist, so I changed it to `get_object_or_404`; there was a block of dead `return render(...)` code at the end that could never be reached, which I removed; and there was a leftover debug `print(vote)`, also removed. I also fixed four `if form.is_valid:` calls that were missing their parentheses (`if form.is_valid():`). The unique constraint added to `Vote` is `UniqueConstraint(('user', 'poll'), name='one_vote_per_user_per_poll')`, which is what the second-layer assertion in Q7 relies on.

There were a few refactors I considered but deliberately did not make (for example splitting the sorting logic in `polls_list`, or adding a repository abstraction to `user_can_vote`). Those changes do not serve testing; the existing mock and spy already cover what I need, and adding more abstraction would only increase the testing burden. I stopped where it was good enough.

---

# Q1 — Linter / Static Review

## Tool chosen: ruff

I used ruff. I chose it because a single binary covers the rules of pyflakes, pycodestyle, isort, and part of pylint; the configuration fits in one section of `pyproject.toml`; and a full scan of the repo in CI takes under a second. I had originally considered flake8 with a few plugins, but its configuration is scattered across `.flake8` and `setup.cfg`, which is more to maintain.

The configuration:

```toml
[tool.ruff]
target-version = "py312"
line-length = 88
exclude = [
    ".venv",
    "*/migrations/*",
    "db.sqlite3",
]

[tool.ruff.lint]
select = ["E", "F", "W", "I", "SIM", "B"]
```

The first run of `ruff check .` reported 27 findings across 7 rule types. Below I write up five of different kinds, and in the end I fixed all of them to green.

## Finding 1: unused import (F401)

File: `accounts/admin.py`, line 1.

Original:

```python
from django.contrib import admin

# Register your models here.
```

ruff output:

```
F401 [*] `django.contrib.admin` imported but unused
 --> accounts/admin.py:1:28
help: Remove unused import: `django.contrib.admin`
```

After:

```python
# Register your models here.
```

This was a placeholder import left by the upstream scaffolding; the whole file never used it.

![Figure 1.1 — F401 unused import](../screenshots/q1_F401.png)

## Finding 2: return the condition directly (SIM103)

File: `polls/models.py`, lines 14–23.

Original:

```python
def user_can_vote(self, user):
    user_votes = user.vote_set.all()
    qs = user_votes.filter(poll=self)
    if qs.exists():
        return False
    return True
```

ruff output:

```
SIM103 Return the condition `not qs.exists()` directly
  --> polls/models.py:21:9
help: Replace with `return not qs.exists()`
```

After:

```python
def user_can_vote(self, user):
    user_votes = user.vote_set.all()
    qs = user_votes.filter(poll=self)
    return not qs.exists()
```

Two fewer lines and more direct. Wrapping a boolean in if-else like this is a common beginner pattern, and ruff catches it precisely.

![Figure 1.2 — SIM103 simplifiable return](../screenshots/q1_SIM103.png)

## Finding 3: variable assigned but never used (F841)

File: `seeder.py`, line 21.

Original:

```python
u = User.objects.create_user(
    first_name=first_name,
    last_name=last_name,
    email=first_name + "." + last_name + "@fakermail.com",
    username=first_name + last_name,
    password="password"
)
```

ruff output:

```
F841 Local variable `u` is assigned to but never used
  --> seeder.py:21:9
help: Remove assignment to unused variable `u`
```

After, I dropped `u = ` and just call it. `u` catches the return value but is never used afterwards. The same file had `c = Choice(...)` and `v = Vote(...)` with the same issue, fixed together.

![Figure 1.3 — F841 unused local variable](../screenshots/q1_F841.png)

## Finding 4: line too long (E501)

File: `polls/views.py`, line 73 (91 characters).

Original:

```python
messages.success(
    request, "Poll & Choices added successfully.", extra_tags=SUCCESS_TAGS)
```

ruff output:

```
E501 Line too long (91 > 88)
  --> polls/views.py:73:89
```

After, each argument on its own line plus a trailing comma:

```python
messages.success(
    request,
    "Poll & Choices added successfully.",
    extra_tags=SUCCESS_TAGS,
)
```

![Figure 1.4 — E501 line too long](../screenshots/q1_E501.png)

## Finding 5: no newline at end of file (W292)

File: `accounts/urls.py`, line 10 (no trailing newline).

Original:

```python
urlpatterns=[
    path('login/', views.login_user, name='login'),
    path('logout/', views.logout_user, name='logout'),
    path('register/', views.create_user, name='register'),
]
```

ruff output:

```
W292 [*] No newline at end of file
  --> accounts/urls.py:10:2
help: Add trailing newline
```

After, I added a newline after `]`. It is almost invisible in a git diff, but some tools (cat, combined diffs) render the missing trailing newline as `\ No newline at end of file`.

![Figure 1.5 — W292 missing trailing newline](../screenshots/q1_W292.png)

## Summary of the five findings

| # | Rule | Type | Fix |
|------|------|------|------|
| 1 | F401 | unused import | remove |
| 2 | SIM103 | simplifiable code | rewrite expression |
| 3 | F841 | unused variable | remove assignment |
| 4 | E501 | line too long | wrap |
| 5 | W292 | missing trailing newline | add newline |

The five rules come from Pyflakes (F), flake8-simplify (SIM), and pycodestyle (E/W). They do not repeat in type and cover five directions: imports, idioms, dead code, style, and file format. It is worth noting that a linter is not a silver bullet: something like `if x is True:` is not caught by ruff's defaults and still needs human review.

---

# Q2 — User Acceptance Testing

## User stories

| ID | User story |
|---|---|
| US-01 | As a guest, I want to register so I can vote on polls. |
| US-02 | As a registered user, I want to log in so I can access poll features. |
| US-03 | As a logged-in user, I want to log out so my session is cleared. |
| US-04 | As a user with poll-add permission, I want to create a poll with at least two choices. |
| US-05 | As a poll owner, I want to edit the poll text. |
| US-06 | As a poll owner, I want to add, edit, and delete choices on my poll. |
| US-07 | As a logged-in user, I want to vote on an active poll exactly once. |
| US-08 | As any user, I want to see live results with vote count and percentage for each choice. |
| US-09 | As any user, I want to browse / search / sort polls so I can find one to vote on. |
| US-10 | As a poll owner, I want to end my poll so no further votes can be cast. |

## Given-When-Then acceptance criteria

**US-01 Register**
- Given I am not logged in
- When I submit a username of 5–100 characters, a valid email, and the same password twice
- Then the system creates the user, redirects to `/accounts/login/`, and shows `Thanks for registering <username>.`

**US-02 Login**
- Given I am registered
- When I POST correct credentials to `/accounts/login/`
- Then I am redirected to the page given by `next` (default `home`), and the navbar shows Logout

**US-03 Logout**
- Given I am logged in
- When I click Logout in the navbar
- Then the session is cleared, I return to `/`, and the navbar shows Login / Register again

**US-04 Create poll**
- Given I am logged in and have the `polls.add_poll` permission
- When I submit a form with poll text and two non-empty choices
- Then one Poll and two Choices are created, I am redirected to `/polls/list/`, and the new poll appears in the list

**US-05 Edit poll**
- Given I am the poll owner
- When I submit edited text
- Then both the list and detail pages show the new text

**US-06 Manage choices**
- Given I am the poll owner
- When I add / edit / delete a choice
- Then the choice count on the edit page changes by +1 / unchanged / -1

**US-07 Vote once**
- Given a poll is active and I have not voted
- When I select a choice on the detail page and submit
- Then a Vote is written to the database and the result page increments that choice by one; a second attempt is blocked with `You already voted this poll!`

**US-08 View results**
- Given a poll has at least one vote
- When I open its result page
- Then each choice shows its count and percentage; when the total is zero all percentages are zero

**US-09 Browse / search / sort**
- Given there are at least 7 polls (pagination triggers)
- When I use the query string `?name` / `?date` / `?vote` / `?search=xxx`
- Then the list sorts by the matching field or filters by keyword, and pagination is preserved

**US-10 End poll**
- Given I am the poll owner and the poll is active
- When I visit `/polls/end/<id>/`
- Then `poll.active=False`, and the detail page from then on renders only the result template (the vote form disappears)

## Four black-box techniques and the cases they produced

| Technique | Where applied | Cases derived |
|---|---|---|
| Equivalence Partitioning (EP) | username length classes (<5 / 5–100 / >100), poll-creation input validity | UAT-001, 002, 015 |
| Boundary Value Analysis (BVA) | the four boundary points 4 / 5 / 100 / 101 of username length | UAT-003, 004, 005, 006 |
| State Transition (ST) | login state machine, voting state machine, poll active→ended | UAT-011, 012, 014 |
| Decision Table (DT) | truth table for registration's three conditions + voting's two conditions | UAT-007, 008, 009, 010, 013 |

The distribution across the 15 cases: EP 3, BVA 4, ST 3, DT 5.

## Registration decision table (basis for UAT-007 to UAT-010)

| Condition | UAT-007 | UAT-008 | UAT-009 | UAT-010 |
|---|---|---|---|---|
| Password match | T | T | T | F |
| Username unique | T | F | T | any |
| Email unique | T | T | F | any |
| Action | create user, go to login | reject: username exists | reject: email registered | reject: password mismatch |

## Voting decision table (basis for UAT-012 / UAT-013)

| Condition | UAT-012 | UAT-013 |
|---|---|---|
| Poll active | T | T |
| Already voted | F | T |
| Action | allow vote, render result | block, redirect with warning |

## UAT test cases

The full fields (description, preconditions, steps, expected, actual, pass/fail) are in `uat/uat_test_cases.xlsx`. The summary table is below; all 15 cases were executed manually and passed.

| ID | Name | Story | Technique | Expected | Result |
|---|---|---|---|---|---|
| UAT-001 | Register with valid mid-range username | US-01 | EP | redirect to login, success message | Pass |
| UAT-002 | Register with too-short username | US-01 | EP | form rejects, no User row | Pass |
| UAT-003 | Register username = 4 chars | US-01 | BVA | form rejects (min_length) | Pass |
| UAT-004 | Register username = 5 chars | US-01 | BVA | registration succeeds | Pass |
| UAT-005 | Register username = 100 chars | US-01 | BVA | registration succeeds | Pass |
| UAT-006 | Register username = 101 chars | US-01 | BVA | form rejects (max_length) | Pass |
| UAT-007 | Register all-valid (happy path) | US-01 | DT | user created, redirect to login | Pass |
| UAT-008 | Register duplicate username | US-01 | DT | reject, 'Username already exists!' | Pass |
| UAT-009 | Register duplicate email | US-01 | DT | reject, 'Email already registered!' | Pass |
| UAT-010 | Register password mismatch | US-01 | DT | reject, 'Password did not match!' | Pass |
| UAT-011 | Login then logout transitions state | US-02, 03 | ST | navbar reflects all 3 states | Pass |
| UAT-012 | Cast first vote on active poll | US-07 | ST | vote recorded, results updated | Pass |
| UAT-013 | Block second vote attempt | US-07 | DT | redirect with warning, no new Vote row | Pass |
| UAT-014 | End an active poll | US-10 | ST | poll.active=False, result template renders | Pass |
| UAT-015 | Create poll with two choices | US-04 | EP | redirect to list, new poll visible | Pass |

The case data lives in a single source file `uat/uat_data.py`. Running `python uat/generate.py` produces an xlsx with two sheets (Test Cases, 15 rows; User Stories, 10 rows). To change a case I edit `uat_data.py` rather than the xlsx directly.

## Execution record

I ran all 15 cases manually in the browser in the order above, completing the steps on the Django dev server, checking against the expected result, and capturing a screenshot of each. All passed, and the actual fields were filled in `uat_data.py` and the xlsx with the real outcomes.

The authored case table:

![Figure 2.1 — UAT case table (authored)](../screenshots/q2_uat_authored.png)

Execution screenshots for the 15 cases:

![UAT-001](../screenshots/uat/UAT-001.png)

![UAT-002](../screenshots/uat/UAT-002.png)

![UAT-003](../screenshots/uat/UAT-003.png)

![UAT-004](../screenshots/uat/UAT-004.png)

![UAT-005](../screenshots/uat/UAT-005.png)

![UAT-006](../screenshots/uat/UAT-006.png)

![UAT-007](../screenshots/uat/UAT-007.png)

![UAT-008](../screenshots/uat/UAT-008.png)

![UAT-009](../screenshots/uat/UAT-009.png)

![UAT-010](../screenshots/uat/UAT-010.png)

![UAT-011](../screenshots/uat/UAT-011.png)

![UAT-012](../screenshots/uat/UAT-012.png)

![UAT-013](../screenshots/uat/UAT-013.png)

![UAT-014](../screenshots/uat/UAT-014.png)

![UAT-015](../screenshots/uat/UAT-015.png)

---

# Q3 — Unit Tests

## Tools

I use Django's built-in test runner for tests and coverage for measuring coverage (HTML report goes to `reports/htmlcov/`). Mocks come from `unittest.mock`; the stub / fake / spy are small classes I wrote myself, kept at the top of `qa_tests/test_unit.py`. I put them in `qa_tests/` rather than `polls/tests.py` so as not to pollute the tests that already ship upstream.

Commands for tests and coverage:

```
python manage.py test qa_tests.test_unit -v 2

coverage run --source=polls,accounts manage.py test qa_tests.test_unit
coverage report
coverage html -d reports/htmlcov
```

## The nine tests

| # | Test method | What it tests | Double | Type |
|---|---|---|---|---|
| 1 | `test_percentages_match_vote_distribution` | vote percentages from `compute_poll_results` | yes | Fake |
| 2 | `test_zero_total_votes_returns_zero_percentage` | percentages return 0 when total is 0 (boundary) | yes | Fake |
| 3 | `test_uses_injected_rng_for_each_result` | `attach_alert_classes` uses the injected rng | yes | Stub |
| 4 | `test_clean_username_rejects_duplicate` | `clean_username` rejects on duplicate | yes | Mock |
| 5 | `test_filters_vote_set_by_poll` | how `Poll.user_can_vote` accesses vote_set | yes | Spy |
| 6 | `test_password_mismatch_attaches_error_to_password2` | registration form, mismatched passwords | no | — |
| 7 | `test_poll_str_returns_text` | `Poll.__str__` | no | — |
| 8 | `test_choice_str_truncates_poll_and_choice_text_to_25` | `Choice.__str__` 25-char truncation | no | — |
| 9 | `test_vote_str_format` | `Vote.__str__` format | no | — |

Five of the nine tests use a double, covering four types (fake / stub / mock / spy), which satisfies the requirement of at least 8 tests, at least 4 using a double, and at least 3 types.

## Notes on each double test

### Tests 1 + 2: Fake

- **Type**: Fake
- **Real dependency replaced**: the Poll/Choice model instances returned by the Django ORM, and the `poll.choice_set.all()` reverse manager
- **Why**: the logic in `compute_poll_results` is pure arithmetic (votes divided by total times 100), but the argument is a model object. Building one means either going through the ORM (hits the DB) or stubbing a pile of attributes. I wrote three small classes — `FakePoll`, `FakeChoiceSet`, `FakeChoice` — that implement the minimal contract ("`choice_set.all()` returns a list, `get_vote_count` returns an int"), which is much simpler than mocking the whole manager
- **How it isolates**: the test never imports `Poll` and never touches the database. The function under test cannot tell whether it received a real Poll or a FakePoll, as long as the object responds to those two methods

### Test 3: Stub

- **Type**: Stub
- **Real dependency replaced**: the `.choice(seq)` method of a `random.Random` instance
- **Why**: the random source makes the alert_class different on every run, so an assertion cannot be pinned down. The stub forces `.choice(seq)` to always return a fixed value so the assertion becomes deterministic
- **How it isolates**: through dependency injection. `attach_alert_classes(results, rng=stub)` passes the stub in as rng; the function uses `rng.choice(...)` internally and does not care whether it got real randomness or a stub. That injection point is the seam left deliberately in R1

### Test 4: Mock

- **Type**: Mock
- **Real dependency replaced**: the `.filter(...).exists()` call chain on `User.objects`
- **Why**: I do not want to create users or stand up a database, and I also want to verify that `clean_username` actually passes `username='alice'` to filter. A Mock can both make `.exists()` return True to trigger a ValidationError and assert the call arguments with `assert_called_once_with(username='alice')`
- **How it isolates**: `@patch("accounts.forms.User.objects")` replaces the symbol inside the forms module, so `clean_username` gets a Mock. The test depends on no real records, runs fast, and does not pollute the database

### Test 5: Spy

- **Type**: Spy
- **Real dependency replaced**: the `user.vote_set.all().filter(poll=...).exists()` chain
- **Why**: beyond making `.exists()` return False, I want to confirm that the function under test really accesses with `filter(poll=self)` and not some other field. A Spy beats a Mock here because it records the argument list for inspection after the test
- **How it isolates**: `SpyVoteSet` implements `all()` / `filter(**kwargs)` / `exists()`, all returning self for chaining, while collecting calls into a `filter_calls` list. Asserting `filter_calls == [{"poll": poll}]` turns "how the code accesses the database internally" into an observable fact, with no DB involved

## Coverage

Coverage after the nine tests (full text in `reports/q3_coverage_report.txt`, HTML in `reports/htmlcov/`):

```
Name                                             Stmts   Miss  Cover
--------------------------------------------------------------------
accounts/forms.py                                   27      2    93%
accounts/views.py                                   29     21    28%
polls/forms.py                                      19      0   100%
polls/models.py                                     43      4    93%
polls/services.py                                   17      1    94%
polls/views.py                                     148    118    20%
--------------------------------------------------------------------
TOTAL                                              364    172    53%
```

Total coverage is 53%. The three modules targeted by the unit tests are all above 90%: `polls/services.py` 94%, `accounts/forms.py` 93%, `polls/models.py` 93%. The low view coverage (polls 20% / accounts 28%) is expected — unit tests deliberately avoid HTTP, and the view layer is left to Q5 (Playwright) and Q7 (integration). This is exactly the layering of the test pyramid.

## Run screenshots

All nine tests passing:

![Figure 3.1 — unit tests green](../screenshots/q3_tests_passing.png)

The coverage HTML report home page:

![Figure 3.2 — coverage report](../screenshots/q3_coverage_html.png)

---

# Q4 — Performance Testing

I use k6 for performance testing (JS scripts, clean CLI output, easy to drop into CI). Two scripts live under `performance/`: `load.js` (sustained 50 VU for 30s) and `stress.js` (VU ramping from 1 up to 200 and back to 0). The target endpoint is `GET /polls/1/` (poll_detail, no `@login_required`, with a `choice_set.count()` plus one vote_set query per choice inside it — a natural N+1 suspect). Before testing I seed a poll with id=1 and 3 choices.

How to run:

```
python manage.py shell < seed_perf.py
python manage.py runserver 127.0.0.1:8000 --noreload &
k6 run --summary-export reports/q4_load_summary.json performance/load.js
k6 run --summary-export reports/q4_stress_summary.json performance/stress.js
```

## Test 1: Load Test (sustained 50 VU)

**Configuration**:

| Item | Value |
|---|---|
| VUs | 50 (constant) |
| Ramp-up | none (instant to 50) |
| Duration | 30 seconds |
| Target | `GET /polls/1/` |
| Thresholds | p(95)<500ms, p(99)<1000ms, error rate<1% |

**Results**:

| Metric | Value |
|---|---|
| Total requests | 2848 |
| Throughput | 93.4 req/s |
| Average response time | 27.51 ms |
| Median | 18.86 ms |
| p(90) | 63.72 ms |
| p(95) | 70.84 ms |
| p(99) | 84.71 ms |
| max | 151.02 ms |
| Error rate | 0.00% (0 / 2848) |

![Figure 4.1 — Load response-time distribution](../screenshots/q4_load_graph.png)

![Figure 4.2 — Load terminal output](../screenshots/q4_load_run.png)

**Interpretation**: 50 VU is the comfort zone for this dev server. p95 at 71ms is nearly an order of magnitude below the 500ms threshold, and p99 at 85ms is more than an order of magnitude below the 1000ms threshold, so baseline capacity is ample. p99 is only 14ms above p95, so the tail is not dramatic (max only reaches 151ms), with zero errors.

## Test 2: Stress Test (1→200 VU)

**Configuration**:

| Item | Value |
|---|---|
| Starting VU | 1 |
| Stages | 15s to 50 → 15s to 100 → 15s to 200 → 15s down to 0 |
| Total duration | 60 seconds |
| Target | `GET /polls/1/` |
| Thresholds | p(95)<2000ms, p(99)<5000ms, error rate<5% |

**Results**:

| Metric | Value |
|---|---|
| Total requests | 21,486 |
| Throughput | 357.6 req/s |
| Average response time | 44.82 ms |
| Median | 25.57 ms |
| p(90) | 108.84 ms |
| p(95) | 126.95 ms |
| p(99) | 222.49 ms |
| max | 661.34 ms |
| Peak VU | 199 |
| Error rate | 0.00% (0 / 21486) |

![Figure 4.3 — Stress response-time distribution](../screenshots/q4_stress_graph.png)

![Figure 4.4 — Stress terminal output](../screenshots/q4_stress_run.png)

**Interpretation**: throughput rose from 93 req/s under load to 358 req/s (3.8x), but latency rose with it:

| Metric | load (50 VU) | stress (200 VU peak) | factor |
|---|---|---|---|
| avg | 27.51 ms | 44.82 ms | 1.6x |
| p95 | 70.84 ms | 126.95 ms | 1.8x |
| p99 | 84.71 ms | 222.49 ms | 2.6x |
| max | 151.02 ms | 661.34 ms | 4.4x |

avg and p95 grew modestly (about 1.8x), but p99 and max grew noticeably (2.6x / 4.4x), which means the pressure lands mainly on tail latency — most requests are fine, while a few start to queue. Zero errors mean the system did not fall over, but the shape of the response-time distribution has changed.

**Where it started to hurt**: after ramping past 100 VU, max climbs sharply (touching 661ms at peak), and p99 doubles while p95 grows only a little — the classic signal of "not crashing but queuing". The cause is the single-threaded Django dev server: `runserver` is one process, one thread, so requests execute in a queue, and each `/polls/1/` request does one `Poll.objects.get` plus one `choice_set.count()`, i.e. two DB round trips, which naturally backs up at 200 VU on a serial queue.

**What I would fix first**, ordered by return on effort:

1. Switch to gunicorn / uvicorn (least effort, most gain). `runserver` in production is demo-only; `gunicorn pollme.wsgi -w 4 --threads 2` raises concurrency to 8 directly, with an expected 3–5x throughput improvement.
2. Fix the N+1 in `poll_detail`. Each choice in the template loop triggers a COUNT query; switching to `Choice.objects.annotate(num_votes=Count('vote'))` does it in one query, taking 3 choices from 3 queries down to 1.
3. Add a template fragment cache. The poll detail is relatively stable during voting, so the page can be cached for a few seconds and skip the database on cache hits under peak load.

---

# Q5 — Web UI Automation

I wrote five end-to-end UI tests with Playwright (Python bindings) plus pytest-django, running a real browser (Chromium headless) and a real Django server (pytest-django's `live_server` fixture).

How to run:

```
pytest qa_tests/ui/
```

Adding `--headed --slowmo 300` shows the browser in action. The five tests run in about 3.8 seconds.

The top of `conftest.py` sets `DJANGO_ALLOW_ASYNC_UNSAFE=true` (required when using Playwright's sync API together with the Django ORM) and provides three fixtures: `alice` (a user with the `polls.add_poll` permission), `sample_poll` (a poll owned by alice with two choices), and `screenshot_dir`. There is also a `login_via_ui` helper that goes through the real login form, reused by the four tests that need an authenticated state.

## The five tests

**Test 1 — `test_register_then_login`**: register a new account → redirect to login → log in with the new account → Logout appears in the navbar, running the whole login state machine. Key assertions:

```python
expect(page).to_have_url(f"{base}/accounts/login/")
expect(page.get_by_role("link", name="Logout")).to_be_visible()
```

![Figure 5.1 — register then login](../screenshots/q5_ui/01_register_then_login.png)

**Test 2 — `test_create_poll`**: after logging in, visit `/polls/add/`, fill the text and two choices, submit, and see the new poll in the list. Note the text field is a textarea, so the selector is `textarea[name='text']`.

![Figure 5.2 — create poll](../screenshots/q5_ui/02_create_poll.png)

**Test 3 — `test_vote_increments_count`**: open the poll detail, select the first choice, submit, and the result page shows "Total: 1 votes".

![Figure 5.3 — vote result](../screenshots/q5_ui/03_vote_result.png)

**Test 4 — `test_double_vote_blocked`**: first seed a Vote via the ORM (alice voted Python), then vote again through the UI, expecting the view to block it, redirect to the list, and flash "You already voted this poll!". This "seed state via ORM, run business via UI" hybrid is much faster than voting twice through the UI, because the focus of the test is whether the second attempt is blocked.

![Figure 5.4 — double vote blocked](../screenshots/q5_ui/04_double_vote_blocked.png)

**Test 5 — `test_owner_deletes_choice`**: as the owner, open the edit page and delete a choice; the list count goes from 2 to 1.

```python
expect(page.locator(".choices li.list-group-item")).to_have_count(2)
# after deleting one choice
expect(page.locator(".choices li.list-group-item")).to_have_count(1)
expect(page.get_by_text("Choice Deleted successfully.")).to_be_visible()
```

![Figure 5.5 — owner deletes choice](../screenshots/q5_ui/05_owner_deletes_choice.png)

Every test involves at least two steps and a real assertion against the resulting page state, not just "open the homepage and check the title". All five tests pass:

![Figure 5.6 — UI tests green](../screenshots/q5_pytest_run.png)

I ran into three snags along the way: first, Playwright's sync API running inside an asyncio context raises `SynchronousOnlyOperation`, solved by that environment variable at the top of conftest; second, the text field is a textarea, not an input; third, the `polls_add` view requires the `polls.add_poll` permission, so I added it to the alice fixture.

---

# Q6 — Smoke Test Plan

## 1. Objective

For this application, a passing smoke test means the latest build has not broken the core functionality on the most common paths, and it is safe to proceed to deeper regression testing. Concretely, all six essential user paths below must work: anyone can open the homepage, a registered user can log in, a logged-in user can see the poll list, a user can enter a poll and vote successfully, a new user can register, and a user can log out. If any one of these breaks, the build does not advance to the next round of testing and is sent back.

## 2. Scope and Coverage

**In scope**: user authentication (register / login / logout), poll list browsing, the single-vote flow, the static homepage.

**Out of scope**: poll and choice CRUD, search/sort/pagination, result-page percentage details, the "already voted" blocking logic, permission boundaries, cross-resolution/browser compatibility, performance.

Rationale: smoke only guards "is the build dead", not "is the feature perfect". CRUD and boundary conditions are for regression testing; smoke should not take half an hour.

## 3. Approach

Hybrid, four automated plus two manual:

| Category | Cases | Tools |
|---|---|---|
| Automated | Home 200, Vote, Register, Logout (three of which reuse Q5 Playwright specs) | Playwright + pytest-django |
| Manual | Login, poll list rendering | browser + checklist |

The automated tests run in seconds in CI and are the norm; the remaining two are checked by eye, because they involve navbar state transitions and list layout — visual confirmations where selectors tend to be flaky, so rather than write brittle selectors I spend 30 seconds looking.

## 4. Test Cases

| ID | Category | Case | Steps | Expected | Pass/Fail criteria |
|---|---|---|---|---|---|
| SMK-01 | auto | Home page 200 | `GET /` | 200, renders navbar and title | HTTP 200 and navbar visible |
| SMK-02 | manual | Login | login page, fill seeded credentials, click Login | redirect to `/`, navbar shows Logout | done within 5s, no 5xx |
| SMK-03 | manual | Poll list renders | after login visit `/polls/list/`, inspect | at least 1 poll item, Add button visible | item count ≥ 1, button visible |
| SMK-04 | auto | Vote flow | login → detail → choose → Submit | result page, "Total: 1 votes" visible | result page visible, count == 1 |
| SMK-05 | auto | Register new user | registration page, fill valid form, Submit | redirect to login, User table +1 | redirect hits login, row exists |
| SMK-06 | auto | Logout | click Logout while logged in | redirect to `/`, navbar back to Login/Register | Login link visible |

All four automated cases reuse the Q5 Playwright specs.

## 5. Test Deliverables

Each smoke run produces: the pytest terminal output (PASS/FAIL per spec), a JUnit XML report (for CI to parse), Playwright traces on failure, the manual checklist results (executor plus timestamp), and a defect ticket opened immediately on any Fail.

## 6. Environment and Resources

The runtime matches CI: Python 3.13, Django 4.2.x, SQLite (in-memory test DB), Chromium headless. It does not connect to a production database; it uses the `live_server` fixture to start an isolated test server. Test data is seeded before each smoke run: one staff user, one regular user, one active poll with 3 choices, written in conftest fixtures and created automatically. Machine requirements: able to run Django plus Chromium, at least 1 GB of memory, no internet needed (except to install dependencies).

## 7. Schedule and Entry / Exit Criteria

**When it runs**: on every push to main, before every PR merge, once manually before cutting a release branch, and after any major dependency upgrade.

**Entry criteria**: code passes ruff lint, `pip install` succeeds, `migrate` runs without error, the dev server starts.

**Exit criteria**: all six cases Pass, pytest exit code 0, both manual checklist items Pass. If any fails, the smoke fails and the build does not proceed downstream.

## 8. Risks and Contingency Plans

| Risk | Impact | Response |
|---|---|---|
| dev server won't start (port conflict / migrate error) | all auto cases fail but not a real bug | pre-run health check: continue only when `curl` returns 200 |
| Chromium not installed properly | errors look like an app bug | CI step `playwright install --with-deps chromium` plus caching |
| manual steps skipped | smoke delayed | checklist in a reminder template, tick in PR comment before release |
| smoke test itself has a bug | false fail blocks the pipeline | any smoke change requires PR review |
| flaky failure (network jitter / slow JS) | trust erodes | re-run manually first; only after three failures in the same place call it a real break |
| nobody reviews manual results | manual becomes meaningless | store results in a signed form / issue for an audit trail |

**Contingency when smoke fails**: immediately label the commit `smoke-fail`, notify the responsible developer and the QA on-call, block any PR depending on that commit, go through the hotfix flow and re-run the same smoke, and if it is a bug in the test itself, QA opens a PR to fix the test.

---

# Q7 — Integration Tests

Unlike Q3, here I use no test doubles at all. Both tests run a real Django test DB, real URL routing, and a real ORM. The file is `qa_tests/test_integration.py`.

How to run:

```
python manage.py test qa_tests.test_integration -v 2
```

The two tests take about 0.15 seconds.

## Test 1: vote de-duplication (View ↔ ORM ↔ DB)

**Components integrated**: the HTTP entry plus Django session/auth, the `poll_vote` view, the `Poll.user_can_vote` application-layer check, the Django ORM, and the `polls_vote` table in SQLite with the unique constraint added in R3.

**What could go wrong if they did not integrate**: if `user_can_vote` had its logic reversed, the view would fail to block the second vote and a duplicate row would enter the database; and if the block existed only in the view without a unique constraint in the DB, any write path that bypasses the view (admin site, migration script, race condition) could produce duplicate rows. This test covers both the view and the DB layers.

```python
def test_second_vote_attempt_blocked_and_db_rejects_raw_duplicate(self):
    url = reverse("polls:vote", kwargs={"poll_id": self.poll.id})

    # 1) first vote goes through the full stack: view -> Vote(...).save() -> DB
    r1 = self.client.post(url, {"choice": self.c1.id})
    self.assertEqual(r1.status_code, 200)
    self.assertEqual(
        Vote.objects.filter(user=self.alice, poll=self.poll).count(), 1
    )

    # 2) second vote is blocked at the view layer: redirect to polls:list
    r2 = self.client.post(url, {"choice": self.c2.id})
    self.assertEqual(r2.status_code, 302)
    self.assertEqual(r2.url, reverse("polls:list"))

    # 3) even bypassing the view with a raw ORM write, the DB constraint raises
    with self.assertRaises(IntegrityError):
        with transaction.atomic():
            Vote.objects.create(
                user=self.alice, poll=self.poll, choice=self.c2
            )

    # 4) the table always has exactly one row
    self.assertEqual(
        Vote.objects.filter(user=self.alice, poll=self.poll).count(), 1
    )
```

The `transaction.atomic()` wrapper is needed because `TestCase` wraps each test method in a transaction; once `IntegrityError` fires, the outer transaction is broken, so the inner savepoint must roll back before the outer one can continue with the later assertions.

## Test 2: registration writes to the user table (Form ↔ User table)

**Components integrated**: the `create_user` view (trimmed in R6), `UserRegistrationForm`'s clean_* and save, Django auth's `create_user`, and the `auth_user` table in SQLite.

**What could go wrong if they did not integrate**: if the form's `save()` did not call `create_user` (e.g. someone changed it to `create` and dropped the password hash), the table would have users with plaintext passwords and login would fail entirely; and if duplicate detection blocked at the form but the view mishandled the invalid form, it would keep flashing errors without creating new rows. The test first checks "valid data → the database really gains a row", then "duplicate username → row count unchanged plus a form error".

```python
def test_form_creates_user_row_and_rejects_duplicate_username(self):
    r1 = self.client.post(self.URL, {
        "username": "alicia",
        "email": "alicia@example.com",
        "password1": "secret",
        "password2": "secret",
    })
    self.assertEqual(r1.status_code, 302)
    self.assertTrue(User.objects.filter(username="alicia").exists())

    before = User.objects.count()
    r2 = self.client.post(self.URL, {
        "username": "alicia",
        "email": "someone-else@example.com",
        "password1": "secret",
        "password2": "secret",
    })
    self.assertEqual(r2.status_code, 200)
    self.assertEqual(User.objects.count(), before)
    self.assertIn(
        "Username already exists!",
        r2.context["form"].errors["username"],
    )
```

The second submission deliberately uses a new email, to make sure what blocks the form is the username check and not the email check.

Compared with the unit tests: Q3 replaces dependencies with fake/stub/mock and runs in 0.002s, testing "is the algorithm correct"; Q7 runs a real ORM and real DB in 0.15s, testing "does the logic still work once wired to Django and the database". Both need testing; neither replaces the other.

Both integration tests pass:

![Figure 7.1 — integration tests green](../screenshots/q7_integration_passing.png)

---

# Q8 — Code Smells

The three smells below are ones I found while reading the code around the lint and unit-test work; they are of three different types. This part is review only — no code changes. The original snippets are the upstream versions pulled with `git show HEAD:`.

## Smell 1: Duplicated Code

| Section | Details |
|---|---|
| Code smell type | Duplicated Code |
| Location | `polls/views.py` lines 72/96/112/129/153/173/196/207 + `accounts/views.py` lines 43/47/51/55/57/63, 14 places total |
| Why it's a smell | The same Bootstrap class string `alert alert-success alert-dismissible fade show` and its warning variant are copied verbatim 14 times across two view files. Upgrading Bootstrap means hunting down every place; tests can only assert against the whole string, and one wrong space breaks them |
| Proposed improvement | Extract Constant: lift the two strings into `SUCCESS_TAGS` / `WARNING_TAGS` in `pollme/messages.py`, imported once per view, so a single change takes effect everywhere |

```python
# polls/views.py:71-73
messages.success(
    request, "Poll & Choices added successfully.", extra_tags='alert alert-success alert-dismissible fade show')

# accounts/views.py:62-64
messages.success(
    request, f'Thanks for registering {user.username}.', extra_tags='alert alert-success alert-dismissible fade show')
```

## Smell 2: Long Method / Multiple Responsibilities

| Section | Details |
|---|---|
| Code smell type | Long Method (multiple responsibilities) |
| Location | `polls/models.py` lines 28–45, `Poll.get_result_dict` |
| Why it's a smell | One method does three things: compute vote percentages, randomly assign Bootstrap colours, and hardcode the colour list inside. The worst part is using `secrets.choice` to pick a random colour — `secrets` is a cryptographic random source, so using it for UI colouring is semantically wrong; and the random source is hardcoded with no injection point, so a unit test cannot predict which alert_class comes out |
| Proposed improvement | Extract Method plus dependency injection: split into `compute_poll_results(poll)` (calculation only) and `attach_alert_classes(results, rng)` (colouring only, rng injectable); passing a stub that returns a fixed value makes the output deterministic in tests |

```python
def get_result_dict(self):
    res = []
    for choice in self.choice_set.all():
        d = {}
        alert_class = ['primary', 'secondary', 'success',
                       'danger', 'dark', 'warning', 'info']
        d['alert_class'] = secrets.choice(alert_class)
        d['text'] = choice.choice_text
        d['num_votes'] = choice.get_vote_count
        if not self.get_vote_count:
            d['percentage'] = 0
        else:
            d['percentage'] = (choice.get_vote_count /
                               self.get_vote_count)*100
        res.append(d)
    return res
```

## Smell 3: Feature Envy

| Section | Details |
|---|---|
| Code smell type | Feature Envy |
| Location | `accounts/views.py` lines 29–65, the `create_user` function body |
| Why it's a smell | This view should only do HTTP orchestration, but it takes over "form validation", which is the form's job: it pulls fields out of cleaned_data by hand, runs three ifs to check password match, duplicate username, and duplicate email, and accumulates results in three flags `check1/check2/check3`. The result is a huge view (37 lines), a near-empty form, validation rules that can only be tested through an HTTP request, and a form that cannot be tested on its own |
| Proposed improvement | Move Method: move the validation back into the form's `clean_username` / `clean_email` / `clean`, add a `save()` wrapping `create_user`, and trim the view to the standard 12-line `if form.is_valid(): form.save()` |

```python
def create_user(request):
    if request.method == 'POST':
        check1 = False
        check2 = False
        check3 = False
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password1 = form.cleaned_data['password1']
            password2 = form.cleaned_data['password2']
            email = form.cleaned_data['email']
            if password1 != password2:
                check1 = True
                messages.error(request, 'Password did not match!', ...)
            if User.objects.filter(username=username).exists():
                check2 = True
                messages.error(request, 'Username already exists!', ...)
            if User.objects.filter(email=email).exists():
                check3 = True
                messages.error(request, 'Email already registered!', ...)
            ...
```

The three flags `check1/check2/check3` are the clearest sign of feature envy — caching another module's validation results in local variables almost always means the logic is in the wrong place.

---

# Q9 — CI/CD Pipeline

The platform is GitHub Actions, configured in `.github/workflows/ci.yml`, a single workflow with a single job that runs Q1 / Q3 / Q4 / Q5 / Q7 in one pass.

## Pipeline steps

| Order | Step | Question | Fail condition |
|---|---|---|---|
| 1 | checkout + Python 3.12 + uv | base | install fails |
| 2 | install project and dependencies | base | requirements fail |
| 3 | `playwright install --with-deps chromium` | Q5 | browser fails |
| 4 | `ruff check .` | Q1 | any lint warning |
| 5 | `manage.py migrate` | base | migration error |
| 6 | `coverage run ... test qa_tests.test_unit` + `coverage report` | Q3 | unit test fails |
| 7 | `manage.py test qa_tests.test_integration` | Q7 | integration fails |
| 8 | `pytest qa_tests/ui/` | Q5 | UI fails |
| 9 | install k6 + seed + start server | Q4 prep | server won't start |
| 10 | `k6 run performance/load.js` | Q4 | p95>500ms or p99>1000ms or error rate>1% |

Any single step failing turns the whole pipeline red, satisfying the requirement to fail the build on lint or test failures. The brief asks for coverage of lint / unit / integration / performance / UI; all five are covered.

The trigger is push to main plus all PRs. Two artifacts (coverage HTML and Playwright screenshots) are uploaded even on failure, to aid diagnosis.

## Demonstrating one green and one red run

The current `ruff check .` is clean, so a normal push runs green. To demonstrate a red run, I deliberately added an unused import to one `.py` file to create an F401; after pushing, the ruff step turned red and the whole build failed; then I removed that line and pushed again, and the pipeline returned to all green.

The all-green run:

![Figure 9.1 — pipeline all green](../screenshots/q9_green_run.png)

The failing run after introducing a lint error:

![Figure 9.2 — lint gate blocks, build fails](../screenshots/q9_red_run.png)

A few trade-offs here: I did not split the job for parallelism (a single job is enough for a student project, and splitting adds yaml complexity for little gain); I did not cache the Playwright browser (about 30 seconds to reinstall each time); I did not add a deploy stage (the brief stops at CI); and performance tests on a GitHub runner have limited CPU, so p95 can vary between runs, which is why the CI threshold leaves a generous margin.

---

# Appendix: Setup and AI Usage Statement

## Environment and running

```bash
uv venv .venv
source .venv/bin/activate
uv pip install -r requirements.txt ruff coverage pytest pytest-django pytest-playwright openpyxl Pillow
playwright install chromium
python manage.py migrate
```

Commands for each kind of test:

| To run | Command |
|---|---|
| ruff lint | `ruff check .` |
| unit tests | `python manage.py test qa_tests.test_unit` |
| integration tests | `python manage.py test qa_tests.test_integration` |
| Playwright UI | `pytest qa_tests/ui/` |
| coverage | `coverage run --source=polls,accounts manage.py test qa_tests.test_unit && coverage report` |
| k6 performance | start the dev server first, then `k6 run performance/load.js` |

## Test count summary

Nine unit tests (five using a test double, covering fake / stub / mock / spy), two integration tests, five Playwright UI tests, two k6 performance scripts, fifteen UAT cases (covering four black-box techniques), plus four refactors made for testability.

## AI Usage Statement

Per the project rules, generative AI is permitted for the application code only. I used AI to assist with a small amount of application-side rewriting (boilerplate during refactoring). The tests, test plans, and analysis are my own work. All external references (Stack Overflow, blog posts, documentation) are cited in place.
