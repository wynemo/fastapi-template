set -e
ruff check --select I --exclude frontend/ --exclude tests/
ruff format . --exclude frontend/ --exclude tests/
PYTHONPATH=$PWD uv run pytest tests --cov=app --cov-report=term-missing --cov-report=html
