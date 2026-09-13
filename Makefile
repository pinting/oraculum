# Builds the published site, and nothing else. Building code is seer's Makefile
# and the kernel's; this asks `make -C seer wasm` for the cross compiled wheel
# and bundles it with the seer sources, the vocabulary and the page.
#
#     make docs          the site, into docs/
#     make -C seer ...   build, wasm, test, run, live
#     make -C kernel ... build, benchmark
#
# Serving it is `python3 -m http.server --directory docs`; the page fetches
# Pyodide itself from a CDN, so nothing here needs a .wasm media type.

include versions.mk

SHELL       := $(BASH)
.SHELLFLAGS := -euo pipefail -c
.ONESHELL:

SEER := seer

# GitHub Pages serves this as the site root when the repository publishes from
# the /docs folder, so committing it is publishing it. Everything this file
# produces is meant to be published, which is why it is written where it is
# published and there is no build directory here.
DOCS := docs
DIST := $(DOCS)/dist

TEMPLATE := $(DOCS)/index.template.html
RUNTIME  := $(DOCS)/runtime.py
PAGE     := $(DOCS)/index.html
RENDER   := $(DOCS)/render.py

VOCABULARY    := vocabulary.tiktoken
SQLGLOT_WHEEL := sqlglot-$(SQLGLOT_VERSION)-py3-none-any.whl

.PHONY: docs

.DEFAULT_GOAL := docs

docs:
	@command -v zip > /dev/null || { echo "Error: zip is not installed"; exit 1; }
	command -v curl > /dev/null || { echo "Error: curl is not installed"; exit 1; }

	$(MAKE) -C $(SEER) wasm

	echo ">> bundling into $(DOCS)/"

	mkdir -p $(DIST)

	# pyodide-build leaves two wheels: one tagged with the Emscripten version
	# it was compiled by, and the same wheel repacked under the Pyodide ABI
	# tag. micropip only accepts the second.
	KERNEL_WHEEL=$$(ls -t $(SEER)/out/wasm/*pyemscripten*.whl 2>/dev/null | head -1)

	if [ -z "$$KERNEL_WHEEL" ]; then
		echo "Error: no Pyodide ABI wheel in $(SEER)/out/wasm - did 'make -C $(SEER) wasm' run?"
		exit 1
	fi

	# A wheel from an earlier build carries a different version in its name, so
	# it would sit here forever rather than being overwritten.
	for STALE in $(DIST)/*.whl; do
		case "$$(basename "$$STALE")" in
			"$$(basename "$$KERNEL_WHEEL")"|"$(SQLGLOT_WHEEL)") ;;
			*) [ -e "$$STALE" ] && rm -f "$$STALE" ;;
		esac
	done

	cp "$$KERNEL_WHEEL" $(DIST)/

	# The wheel is published beside the page rather than resolved by micropip
	# in the browser, and because it is published it is committed - so a fresh
	# clone already has it and downloads nothing.
	if [ ! -f "$(DIST)/$(SQLGLOT_WHEEL)" ]; then
		echo ">> fetching $(SQLGLOT_WHEEL)"

		URL=$$(curl -sSL $(PYPI)/pypi/sqlglot/$(SQLGLOT_VERSION)/json \
			| python3 -c "import json, sys; print(next((r['url'] for r in json.load(sys.stdin)['urls'] if r['filename'] == '$(SQLGLOT_WHEEL)'), ''))")

		if [ -z "$$URL" ]; then
			echo "Error: $(SQLGLOT_WHEEL) is not on $(PYPI)"
			exit 1
		fi

		curl -sSL -o "$(DIST)/$(SQLGLOT_WHEEL).part" "$$URL"
		mv "$(DIST)/$(SQLGLOT_WHEEL).part" "$(DIST)/$(SQLGLOT_WHEEL)"
	fi

	# test.py and cases.yaml ride along so the corpus can be run in the browser.
	echo ">> packing the seer sources"

	rm -f $(DIST)/seer.zip.part

	zip -q -r $(DIST)/seer.zip.part \
		$(SEER)/src $(SEER)/core.py $(SEER)/main.py $(SEER)/schema.sql \
		$(SEER)/test.py $(SEER)/cases.yaml \
		-x '*__pycache__*' '*.pyc'

	mv $(DIST)/seer.zip.part $(DIST)/seer.zip

	cp $(VOCABULARY) $(DIST)/

	# Every version the build pinned, so the page installs those rather than
	# whatever is current.
	printf '%s\n' \
		'{' \
		'  "python": "$(PYTHON_VERSION)",' \
		'  "pyodide": "$(PYODIDE_VERSION)",' \
		'  "pyodide_cdn": "$(PYODIDE_CDN)",' \
		'  "pyodide_build": "$(PYODIDE_BUILD_VERSION)",' \
		'  "xbuildenv": "$(XBUILDENV_VERSION)",' \
		'  "emscripten": "$(EMSCRIPTEN_VERSION)",' \
		"  \"kernel_wheel\": \"$$(basename "$$KERNEL_WHEEL")\"," \
		'  "sqlglot_wheel": "$(SQLGLOT_WHEEL)",' \
		'  "numpy": "$(NUMPY_VERSION)"' \
		'}' > $(DIST)/manifest.json

	echo ">> rendering the page"

	python3 $(RENDER) $(TEMPLATE) $(SEER)/schema.sql $(RUNTIME) $(PAGE)

	# Jekyll would otherwise run over the site on publish, and it drops files
	# whose names begin with an underscore.
	touch $(DOCS)/.nojekyll

	echo
	echo "$(DOCS)/ is the site - commit it and GitHub Pages serves it:"
	du -b $(PAGE) $(DIST)/* | awk '{printf "  %-58s %10s\n", $$2, $$1}'
	echo
	echo "locally: python3 -m http.server --directory $(DOCS)"
