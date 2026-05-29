# Django Poll App — SQA Assignment

A QA assignment built on [devmahmud/Django-Poll-App](https://github.com/devmahmud/Django-Poll-App). I refactored a few testability issues and wrote a full testing suite: linting, unit tests, integration tests, UI automation, performance tests, plus a CI/CD pipeline.

## Getting started

```bash
# 1) create a venv and install dependencies
uv venv .venv
source .venv/bin/activate
uv pip install -r requirements.txt ruff coverage pytest pytest-django pytest-playwright openpyxl Pillow
playwright install chromium

# 2) database
python manage.py migrate

# 3) start the dev server (optional)
python manage.py runserver
```

## Running the tests

| What to run | Command |
|---|---|
| ruff lint | `ruff check .` |
| unit tests | `python manage.py test qa_tests.test_unit` |
| integration tests | `python manage.py test qa_tests.test_integration` |
| Playwright UI | `pytest qa_tests/ui/` |
| coverage | `coverage run --source=polls,accounts manage.py test qa_tests.test_unit && coverage report` |
| k6 performance | start the dev server first, then `k6 run performance/load.js` |
| run everything (Q3 + Q7) | `python manage.py test qa_tests` |

## Deliverables index

The full write-up for every question is in the report document submitted on Canvas. This table maps each question to the code and artifacts in this repo:

| Question | Main artifacts in repo |
|---|---|
| Q1 Linter | [pyproject.toml](pyproject.toml), [q1_ruff_full_output.txt](reports/q1_ruff_full_output.txt) |
| Q2 UAT | [uat/uat_test_cases.xlsx](uat/uat_test_cases.xlsx), [uat/uat_data.py](uat/uat_data.py) |
| Q3 Unit tests | [qa_tests/test_unit.py](qa_tests/test_unit.py), [htmlcov/](reports/htmlcov/index.html), [q3_coverage_report.txt](reports/q3_coverage_report.txt) |
| Q4 Performance | [performance/load.js](performance/load.js), [performance/stress.js](performance/stress.js), summary JSON + raw output under [reports/](reports/) |
| Q5 UI Automation | [qa_tests/ui/](qa_tests/ui/) (5 Playwright tests + conftest) |
| Q6 Smoke Plan | document only |
| Q7 Integration | [qa_tests/test_integration.py](qa_tests/test_integration.py) |
| Q8 Code Smells | review only (maps to refactors R1/R4/R6) |
| Q9 CI/CD | [.github/workflows/ci.yml](.github/workflows/ci.yml) |

## Refactoring summary

Four refactors made for testability, each serving one or more questions:

| ID | Files | What changed | Questions served |
|---|---|---|---|
| R1 | `polls/models.py` + `polls/services.py` (new) | split `get_result_dict` into `compute_poll_results` + `attach_alert_classes`, with an injectable RNG | Q3 (stub/fake), Q8 (long method) |
| R3 | `polls/views.py` + `polls/migrations/0003_*` | fixed 3 bugs in `poll_vote` + added a `Vote` UniqueConstraint | Q1 (lint), Q7 (DB constraint test) |
| R4 | `pollme/messages.py` (new) | extracted `SUCCESS_TAGS` / `WARNING_TAGS` shared constants | Q8 (duplicated code) |
| R6 | `accounts/forms.py` + `accounts/views.py` | moved registration validation from the view into the form's clean_* | Q3 (mock), Q8 (feature envy) |

## Test count

- **9 unit tests** (5 of which use a test double: 1 fake / 1 stub / 1 mock / 1 spy + 1 zero-vote boundary)
- **2 integration tests** (view↔DB vote de-duplication + form↔User table registration)
- **5 Playwright UI tests** (register/login/create/vote/double-vote/delete-choice)
- **2 k6 performance scripts** (load 50 VU 30s + stress 1→200 VU 60s)
- **15 UAT test cases** (covering 4 black-box techniques, distributed 3+4+3+5)
- **16 automated tests total + 15 manual UAT cases**

## Project structure

```
django_poll_refactored/
├── .github/workflows/ci.yml          # Q9
├── accounts/                          # upstream + R6 refactor
├── polls/                             # upstream + R1, R3 refactors
│   ├── services.py                    # added in R1
│   └── migrations/0003_vote_unique_user_poll.py  # added in R3
├── pollme/
│   └── messages.py                    # added in R4
├── performance/
│   ├── load.js                        # Q4
│   └── stress.js                      # Q4
├── qa_tests/
│   ├── test_unit.py                   # Q3
│   ├── test_integration.py            # Q7
│   └── ui/                            # Q5
│       ├── conftest.py
│       └── test_*.py (5 files)
├── reports/                           # all write-ups
├── screenshots/                       # all screenshots
├── scripts/                           # small helpers for rendering graphs
├── uat/
│   ├── uat_data.py                    # Q2 data source
│   ├── generate.py                    # Q2 xlsx generator
│   └── uat_test_cases.xlsx            # Q2 main deliverable
└── pyproject.toml                     # ruff + pytest config
```

## CI/CD demo flow

1. Create your own GitHub repo (do not use the upstream remote).
2. `git remote set-url origin <your repo>`, then `git add -A && git commit && git push -u origin master` (the workflow listens on both `main` and `master`).
3. GitHub Actions runs automatically. Since `ruff check .` is currently clean, this run is **green**.
4. Deliberately add an unused import (to create an F401) and push — this run is **red**, demonstrating the lint gate.
5. Revert that line and push — back to **green**.
6. Capture one screenshot each into `screenshots/q9_{red,green}_run.png`.

## AI Usage Statement

Per the project rules, generative AI is permitted for the application code only. I used AI to assist with a small amount of application-side rewriting (boilerplate during refactoring). The tests, test plans, and analysis are my own work. All external references are cited in their respective write-ups.
