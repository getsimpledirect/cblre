# Contributing to cblre

## Commit convention

All commits must follow [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/).
Releases are automated from commit messages via release-please — the commit
type determines what version component gets bumped.

### Types

| Type       | When to use                                        | Version bump  |
|------------|----------------------------------------------------|---------------|
| `feat`     | New scorer, new track, new model client            | minor         |
| `fix`      | Bug fix in harness logic, scorer, or judge         | patch         |
| `docs`     | Documentation only                                 | patch         |
| `chore`    | Tooling, CI, dependencies, release config          | patch         |
| `refactor` | Code restructure with no behaviour change          | patch         |
| `test`     | Adding or fixing tests                             | patch         |
| `ci`       | GitHub Actions workflows only                      | patch         |
| `perf`     | Performance improvement                            | patch         |

### Format

```
<type>(<optional scope>): <short subject>

<One or two sentence introduction summarising what the commit delivers.>

- <bullet point — one idea per bullet>
- <bullet point>

BREAKING CHANGE: <description>   ← include only when present; triggers major bump
```

**Rules:**
- Subject line: imperative mood, no trailing period, max 72 characters.
- Body: one intro sentence, then bullet points. No paragraph blocks, no code
  fences inside the message body.
- `BREAKING CHANGE` footer triggers a major version bump regardless of type.

### Examples

```
feat(scorers): add keyword_coverage track scorer

Adds a new programmatic scorer that measures keyword coverage over
model responses for terminology-heavy regulatory items.

- Implements KeywordCoverageScorer with configurable threshold
- Registers scorer under the keyword_coverage track key
- Adds unit tests with synthetic item fixtures
```

```
fix(judge): handle empty response string in rubric scorer

Prevents a KeyError crash when the model returns an empty string
for a rubric-scored item.

- Guards against empty response before rubric extraction
- Returns score=0 with a note rather than raising
```

## Releases

Releases are **PR-gated via release-please**. On every push to `main`,
release-please maintains an open release PR that accumulates all pending
changes in `CHANGELOG.md`. Merging that PR:

1. Bumps the version in `pyproject.toml`.
2. Creates a git tag (`vX.Y.Z`).
3. Creates a GitHub Release with auto-generated release notes.

**No PyPI publishing** — cblre is installed directly from GitHub:

```
pip install "cblre @ git+https://github.com/getsimpledirect/cblre.git"
```

No extra secrets are required; the workflow uses the built-in
`GITHUB_TOKEN`.

## What not to touch

The following are out of scope for external contributions without explicit
maintainer approval:

- `harness/scorers.py` — programmatic scoring logic
- `harness/judge.py` — LLM judge integration
- `schema/eval_item.schema.json` — item format
- `data/` — evaluation items and gold answers (most of this directory is
  gitignored; only the public synthetic sample is committed)

## Running CI locally

```
pip install -e .
python -c "from harness import scorers, judge, run_eval, models, stats"
python -m harness.run_eval --help
```
