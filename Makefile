.PHONY: build clean sync-dev test ci publish update-pele

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

# Vendored Mermaid renderer (src/foliate/pele/). After bumping, also bump
# BUILD_SCHEMA_VERSION in src/foliate/cache.py so cached pages re-render.
PELE_VERSION := 1.10.0

update-pele:
	tmp=$$(mktemp -d) && \
	npm pack --silent --pack-destination "$$tmp" pele@$(PELE_VERSION) >/dev/null && \
	tar -xzf "$$tmp/pele-$(PELE_VERSION).tgz" -C "$$tmp" && \
	{ printf '/*! Pele $(PELE_VERSION) | MIT License | https://github.com/obsidianmd/pele */\n'; \
	  cat "$$tmp/package/dist/pele.js"; } > src/foliate/pele/pele.mjs && \
	cp "$$tmp/package/LICENSE" src/foliate/pele/LICENSE && \
	rm -rf "$$tmp"
