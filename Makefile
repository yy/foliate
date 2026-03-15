.PHONY: build clean sync-dev test ci publish

sync-dev:
	uv sync --frozen --extra dev

build: clean
	uv build

clean:
	rm -rf dist/*.whl dist/*.tar.gz

test: sync-dev
	uv run pytest

ci: sync-dev
	uv run mypy src/foliate
	uv run pytest -q
	uv build

publish: build
	uv publish
