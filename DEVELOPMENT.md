# Development Guide

Everything a contributor needs to set up a local environment, run tests, and understand the project structure.

---

## Prerequisites

- Python 3.10, 3.11, or 3.12
- Git

No GPU, no API keys, and no external services are required to run the test suite or work on the harness code.

---

## Local setup

```bash
git clone https://github.com/getsimpledirect/cblre.git
cd cblre

# Editable install — harness/ is importable as a package immediately
pip install -e .

# Install test runner
pip install pytest

# Smoke-test the install
python -c "from harness import scorers, judge, run_eval, models, stats"
cblre-eval --help
```

### Optional extras

```bash
# Vertex AI judge path (GCP ADC auth — adds google-cloud-aiplatform)
pip install -e ".[vertex]"

# Local HuggingFace checkpoint evaluation (adds torch, transformers, peft)
pip install -e ".[local]"
```

---

## Running the test suite

```bash
python -m pytest -q                        # full suite, quiet output
python -m pytest -v                        # verbose (shows every test name)
python -m pytest tests/test_scorers.py     # single file
python -m pytest -k "test_mcq"             # tests matching a keyword
```

The full suite runs in under 10 seconds with no network calls, no GPU, and no API keys.

**Test files and what they cover:**

| File | Module | Key scenarios |
|---|---|---|
| `tests/test_scorers.py` | `harness/scorers.py` | All 7 scorers, extraction patterns, needs_judge gate |
| `tests/test_stats.py` | `harness/stats.py` | Bootstrap CI/diff, parity ratio, edge cases |
| `tests/test_judge.py` | `harness/judge.py` | Rubric prompt, JSON parsing, ensemble voting |
| `tests/test_run_eval.py` | `harness/run_eval.py` | load/score/aggregate, all scoring paths |
| `tests/test_models.py` | `harness/models.py` | build_client factory, static helpers, client init |

---

## Project structure

```
cblre/
├── harness/                # The scoring harness (published, Apache 2.0)
│   ├── __init__.py
│   ├── models.py           # Model clients (OpenAI-compat, Anthropic, Vertex, HF local)
│   ├── scorers.py          # Programmatic scorers (mcq_exact, citation_validity, …)
│   ├── judge.py            # LLM-as-judge: rubrics, ensemble, fabrication cap
│   ├── run_eval.py         # CLI entry point + aggregation
│   └── stats.py            # Bootstrap CI, diff test, parity ratio
├── tests/                  # Pytest test suite
├── schema/
│   └── eval_item.schema.json   # Item format (JSON Schema)
├── data/
│   └── sample/             # Synthetic illustrative items (NOT scoring items)
├── docs/
│   ├── quickstart.md       # 5-minute end-to-end guide
│   ├── methodology.md      # Scoring protocol and design decisions
│   └── data_access.md      # How to request the gated item bank
└── .github/
    ├── ISSUE_TEMPLATE/     # Bug report, feature request, access request
    └── workflows/          # CI (pytest) and release-please automation
```

---

## Commit conventions

See [CONTRIBUTING.md](CONTRIBUTING.md#commit-convention). The short version:

```
<type>(<scope>): <subject>

One intro sentence.

- bullet point
- bullet point
```

Types: `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `ci`, `perf`.

---

## What requires maintainer approval

The following files must not be changed without explicit maintainer approval — changes affect scoring validity and may invalidate published benchmark numbers:

- `harness/scorers.py` — programmatic scoring logic
- `harness/judge.py` — LLM judge rubrics and ensemble logic
- `schema/eval_item.schema.json` — item format
- `data/` — item content (most of this directory is gitignored)

Everything else — model clients, CLI, statistics, documentation, CI — is open for contribution via the normal PR flow.

---

## Release process

Releases are automated via [release-please](https://github.com/googleapis/release-please). On every push to `main`, release-please maintains an open release PR that accumulates changes in `CHANGELOG.md`. Merging that PR bumps the version, tags the commit, and creates a GitHub Release.

No manual version bumps or PyPI publishing are needed.

---

## Coding style

- **Formatter / linter:** `ruff` (line length 100, single quotes) — run `ruff check harness/ tests/` locally
- **Type hints:** used throughout; `from __future__ import annotations` in every module
- **Comments:** only when the *why* is non-obvious — no docstrings restating the function name
- **Test naming:** `test_<thing>_<condition>` — readable as a specification
