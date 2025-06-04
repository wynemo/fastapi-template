set -e
ruff check --select I --exclude frontend/ --exclude tests/
ruff format . --exclude frontend/ --exclude tests/
