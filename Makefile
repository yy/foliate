.PHONY: build clean test publish

build: clean
	uv build

clean:
	rm -rf dist/*.whl dist/*.tar.gz

test:
	uv run pytest

publish: build
	uv publish
