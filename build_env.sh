#!/bin/bash

# Create the virtual environment in the specified path
uv venv --python 3.12 .venv

# Activate the virtual environment (Unix)
source .venv/bin/activate

# Install all dependencies, including the 'dev' group
uv pip install -e ".[dev]"

# Install pre-commit hooks and run tests
pre-commit install
pytest