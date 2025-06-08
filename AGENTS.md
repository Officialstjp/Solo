# AGENTS.md — Project-wide Instructions for Codex
# Scope: entire repository

## 1. Environment
- **Primary OS**: Windows 11; WSL 2 Ubuntu 22.04 allowed for Linux-only tooling.
- **Languages**: Python 3.11.9 (main), PowerShell for ops scripts.
- **Editor context**: VS Code tasks and launch configs preferred; Visual Studio optional.

## 2. Style Guide
- **Identifier casing**: PascalCase for classes, functions, variables; UPPER_SNAKE for constants.
- **Top-of-file banner** in every code file:

  ```python
  """
  Module Name: <file>
  Purpose   : <short blurb>
  Params    : <key parameters>
  History   : <YYYY-MM-DD> <author> – <change>
  """
  ```
  Sectioned comments:
  ``` Python
	# ===== functions =====
	# ---- helper functions ----
	...
	# ==== runtime ====
	# ---- Init ----
	...
	# ---- main loop ----
	...
	Formatting: PEP 8 base with 4-space indent, ≤ 120 chars/line, trailing commas allowed.
	```

## 3. Workflow & Git
- **Branches**: feature-<slug> for enhancements, bugfix-<slug> for fixes.

- **Commits**: <type>: <subject> using feat|fix|docs|chore|refactor|test.

-**Pull Requests**: always open as draft; wait for manual approval by Stefan.

## 4. Testing & Quality Gates
- **Run tests**: pytest -q.

- **Lint**: flake8 . --max-line-length 120.

- **Security**: run bandit -r . -ll; block merge on Medium or higher severity.

- **Coverage**: target ≥ 80 %; fail build below that.

## 5. CI / CD
- **CI platform**: GitHub Actions (.github/workflows/ci.yml).

- **Secrets**: reference via ${{ secrets.* }}; never hard-code.

- **Deployment**: on main push; use environment: production with required reviewers.

## 6. Assistant Behaviour
- **Explain first**: provide a succinct plan before editing more than one file.

- **Detail rationale**: accompany every patch with reasoning I can learn from.

- **Ask when unsure**: if tests fail or ambiguity arises, pause and request guidance.

- **No auto-merge**: human approval is mandatory for every PR.

## 7. Misc
- **Timeouts**: if a single command may exceed 5 min, surface a progress notice.

- **External services**: may call public APIs or OpenAI tools as needed; prefer official docs.

- **Docs output**: Markdown (.md) for all generated docs & READMEs.
