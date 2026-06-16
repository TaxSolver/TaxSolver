# Contributing to TaxSolver

Thanks for your interest in improving TaxSolver! This document explains how to
set up a development environment, the conventions we follow, and how to submit
changes.

## Getting started

1. Fork the repository and clone your fork.
2. Create a development environment and install the package in editable mode
   with the development extras:

   ```bash
   git clone https://github.com/Tax-Lab/TaxSolver.git
   cd TaxSolver
   pip install -e ".[dev]"
   ```

   The project also ships a `uv.lock`; if you use [uv](https://docs.astral.sh/uv/)
   you can run `uv sync` instead.

3. Install the pre-commit hooks so linting and formatting run automatically:

   ```bash
   pre-commit install
   ```

## Development workflow

- Create a feature branch off `main` (e.g. `git checkout -b fix/my-change`).
- Keep commits focused and write descriptive commit messages that explain the
  *why* of a change, not just the *what*.
- Add or update tests for any behavior you change.

## Code style and quality

We use [ruff](https://docs.astral.sh/ruff/) for linting and formatting, wired
up through pre-commit. Before pushing, make sure the checks pass:

```bash
ruff check .
ruff format --check .
```

Type checking uses [mypy](https://mypy-lang.org/):

```bash
mypy src
```

## Running the tests

The test suite uses [pytest](https://docs.pytest.org/):

```bash
pytest
```

Some end-to-end tests can use the Gurobi backend and will be skipped
automatically if no Gurobi license/environment is available. The default
backend (CVXPY + HiGHS) requires no license.

## Submitting changes

1. Ensure the full test suite and pre-commit checks pass locally.
2. Push your branch and open a pull request against `main`.
3. Describe the motivation for the change and reference any related issues.

## Reporting issues

Please report bugs and request features on
[GitHub Issues](https://github.com/Tax-Lab/TaxSolver/issues). For bug reports,
include a minimal reproducible example and the versions of TaxSolver and your
solver backend.
