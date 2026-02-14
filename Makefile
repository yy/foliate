.PHONY: build clean test ci publish

build: clean
	uv build

clean:
	rm -rf dist/*.whl dist/*.tar.gz

test:
	uv run pytest

ci:
	uv run pytest -q
	uv build

publish: build
	uv publish
