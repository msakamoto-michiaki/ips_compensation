SHELL := /bin/bash

MAIN      ?= main.tex
BUILD_DIR ?= build
FONT_DIR  ?= fonts

# system: ./fonts を使わない（TeX Live/OS のフォントを直接使う）
# local : ./fonts にコピーして Path=fonts/ で使う
FONT_MODE ?= system

# local のときだけ有効: harano / noto
FONTSET   ?= harano

LATEXMK ?= latexmk
LATEXMK_FLAGS ?= -lualatex -interaction=nonstopmode -halt-on-error -file-line-error

JOB := $(basename $(notdir $(MAIN)))
PDF := $(BUILD_DIR)/$(JOB).pdf
FDB := $(BUILD_DIR)/$(JOB).fdb_latexmk
LOG := $(BUILD_DIR)/$(JOB).log

.PHONY: all pdf fonts fonts-harano fonts-noto clean distclean

all: pdf

$(BUILD_DIR):
	mkdir -p "$(BUILD_DIR)"

$(FONT_DIR):
	mkdir -p "$(FONT_DIR)"

# ---- single fonts rule (no duplicate, no warnings) ----
fonts:
	@if [ "$(FONT_MODE)" = "local" ]; then \
	  $(MAKE) fonts-$(FONTSET); \
	else \
	  echo "[fonts] FONT_MODE=$(FONT_MODE): skip (use system/texlive fonts)"; \
	fi

# ---- local: HaranoAji from TeX Live -> ./fonts ----
fonts-harano: | $(FONT_DIR)
	@bash -euo pipefail -c '\
	  for f in HaranoAjiMincho-Regular.otf HaranoAjiMincho-Bold.otf HaranoAjiGothic-Regular.otf HaranoAjiGothic-Bold.otf; do \
	    p="$$(kpsewhich "$$f" 2>/dev/null || true)"; \
	    [[ -n "$$p" ]] || { echo "ERROR: $$f not found (install collection-langjapanese etc.)"; exit 1; }; \
	    cp -f "$$p" "$(FONT_DIR)/$$f"; \
	    echo "COPIED: $$f"; \
	  done'

# ---- local: Noto from OS -> ./fonts (必要なら候補追加) ----
fonts-noto: | $(FONT_DIR)
	@bash -euo pipefail -c '\
	  find_one() { \
	    for pat in "$$@"; do \
	      p="$$(find /usr/share/fonts /usr/local/share/fonts -type f -name "$$pat" -print -quit 2>/dev/null || true)"; \
	      [[ -n "$$p" ]] && { echo "$$p"; return 0; }; \
	    done; \
	    return 1; \
	  }; \
	  for item in \
	    "NotoSerifCJKjp-Regular.otf:NotoSerifCJKjp-Regular.otf NotoSerifCJK-Regular.ttc NotoSerifCJK.ttc" \
	    "NotoSerifCJKjp-Bold.otf:NotoSerifCJKjp-Bold.otf NotoSerifCJK-Bold.ttc NotoSerifCJK.ttc" \
	    "NotoSansCJKjp-Regular.otf:NotoSansCJKjp-Regular.otf NotoSansCJK-Regular.ttc NotoSansCJK.ttc" \
	    "NotoSansCJKjp-Bold.otf:NotoSansCJKjp-Bold.otf NotoSansCJK-Bold.ttc NotoSansCJK.ttc" \
	  ; do \
	    dst="$${item%%:*}"; pats="$${item#*:}"; \
	    src="$$(find_one $$pats)" || { echo "ERROR: $$dst not found in OS fonts"; exit 1; }; \
	    cp -f "$$src" "$(FONT_DIR)/$$dst"; echo "COPIED: $$dst"; \
	  done'

# ---- Build ----
pdf: | $(BUILD_DIR)
	@$(MAKE) fonts
	@# latexmk が「前回の失敗」を覚えて止まるのを防ぐ
	@rm -f "$(FDB)" "$(LOG)"
	@$(LATEXMK) $(LATEXMK_FLAGS) -outdir="$(BUILD_DIR)" "$(MAIN)"
	@echo "OK: $(PDF)"

clean:
	@$(LATEXMK) -C -outdir="$(BUILD_DIR)" "$(MAIN)" >/dev/null 2>&1 || true
	@rm -rf "$(BUILD_DIR)"
	@echo "cleaned"

distclean: clean
	@rm -rf "$(FONT_DIR)"
	@echo "removed fonts dir"

