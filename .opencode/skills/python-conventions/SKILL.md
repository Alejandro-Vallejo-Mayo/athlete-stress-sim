---
name: python-conventions
description: Code conventions and standards for athlete-stress-sim (PEP 8, PEP 257 docstrings, full English wording, strict typing). Use when writing, reviewing, refactoring, or generating any Python source, tests, docstrings, comments, identifiers, build files (Makefile, Docker, CI) or config comments in this repository.
---

# Python & project code conventions

Project-wide standards for **athlete-stress-sim**. Every code artifact must comply.

## 1. Language: English everywhere in code

- Identifiers, comments, docstrings, log/error messages, test names, commit
  messages, branch names, and config/build comments are written in **English**.
- Public documentation under `docs/` (product requirements, roadmap, user guide,
  architecture, mathematical model and validation) is written in **English**.
- The public portfolio `README.md` is written in English (roadmap S16).

## 2. Style: PEP 8, enforced by ruff

- Formatter/linter is **ruff**; do not hand-format. Run `make format` before
  committing.
- `line-length = 100` (see `pyproject.toml`). No trailing whitespace, single
  trailing newline per file.
- 4-space indentation, spaces around operators, two blank lines between
  top-level definitions, one between methods.
- Prefer clear names over comments: `snake_case` for functions/variables,
  `PascalCase` for classes, `UPPER_SNAKE_CASE` for constants, `_leading` for
  private helpers.
- Do not shadow builtins or use ambiguous names (`data`, `tmp`, `f`, `l`).
- Keep functions small and single-purpose (ruff `PL` rules are enabled).

## 3. Docstrings: PEP 257

- **Every module, public class, and public function has a docstring.**
- First line: imperative mood, ends with a period, fits on one line.
  Examples: `"""Return the backend liveness status."""`,
  `"""Parse a FIT file into second-by-second samples."""`
- Multi-line docstrings: summary line, blank line, then details; closing `"""`
  on its own line.
- For functions with parameters or returns, use **Google-style** sections:

  ```python
  def trimp(duration_min: float, hr_avg: float, hr_rest: int, hr_max: int) -> float:
      """Compute Banister's TRIMP for a running session.

      Args:
          duration_min: Session duration in minutes.
          hr_avg: Average heart rate during the session (bpm).
          hr_rest: Resting heart rate (bpm).
          hr_max: Maximum heart rate (bpm).

      Returns:
          The TRIMP value in arbitrary units.

      Raises:
          ValueError: If ``hr_max`` is not greater than ``hr_rest``.
      """
  ```

- Document math with the symbol names used in the PRD (e.g. ``HR_max``,
  ``tau_1``) and reference the requirement (`RF-xx` / `RNF-xx`) when relevant.

## 4. Typing: strict mypy

- Every new public function/method is fully annotated (arguments + return).
- The repo runs `mypy --strict` (config in `pyproject.toml`); no untyped defs.
- Add `from __future__ import annotations` at the top of every module.
- Prefer built-in generics (`list[str]`, `dict[str, float]`, `X | None`).
- Do not use `Any` as a shortcut; if a third-party stub is missing, add it to
  the `[[tool.mypy.overrides]]` list instead of sprinkling `# type: ignore`.
- Avoid bare `# type: ignore`; if unavoidable, specify the error code.

## 5. Imports

- Grouped and sorted by ruff/isort: **stdlib → third-party → first-party**,
  each group separated by a blank line.
- Import project code with absolute paths: `from athlete_stress_sim.core...`.
- No wildcard imports (`from x import *`), no relative imports across packages.

## 6. Comments

- Comments explain **why**, not **what**. If the code needs a "what" comment,
  refactor the code instead.
- No commented-out code, no decorative banners, no `TODO` without an owner/issue.
- Keep comments in English and next to the line they describe.

## 7. Errors, logging and secrets

- Raise specific exceptions with actionable messages; never `except:` or
  `except Exception: pass`.
- Use the `logging` module; never `print()` in library code.
- Never hard-code credentials or tokens. Read them via
  `athlete_stress_sim.backend.config` (pydantic-settings + `.env`).
- `.env` is git-ignored; only `.env.example` (placeholders) is committed.

## 8. Tests

- Framework: **pytest** (`testpaths = ["tests"]`, `pythonpath = ["src"]`).
- File `tests/test_<module>.py`, function `test_<behavior>`.
- Follow Arrange-Act-Assert; one behavior per test; names describe the expected
  outcome, not the implementation.
- Use fixtures for sample `.FIT`/telemetry data; keep them in `tests/`.
- Coverage target: **≥ 80 %** on `src/athlete_stress_sim/core`
  (`make test-cov`).

## 9. Project layout

- Single package, *src layout*: `src/athlete_stress_sim/` with `backend/`,
  `core/` (`etl/`, `metrics/`, `models/`) and `frontend/`.
- Every package directory has an `__init__.py`.

## 10. Tooling (single entry point: the Makefile)

| Task        | Command           |
| ----------- | ----------------- |
| Format      | `make format`     |
| Lint        | `make lint`       |
| Typecheck   | `make typecheck`  |
| Test        | `make test`       |
| Coverage    | `make test-cov`   |

`pre-commit` runs ruff + ruff-format + mypy on commit; CI runs
`make lint`, `make typecheck` and `make test`. A change is not done until all
three pass.

## 11. Pre-delivery checklist

- [ ] All identifiers, comments and docstrings are in English.
- [ ] Every module/class/function has a PEP 257 docstring.
- [ ] Public APIs are fully type-annotated and pass `make typecheck`.
- [ ] `make lint` and `make test` pass.
- [ ] No secrets, no `print()`, no commented-out code.
