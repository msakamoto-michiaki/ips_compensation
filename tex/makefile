# ===== Makefile for (u)platex + dvipdfmx via latexmk =====

# メインtex（拡張子なし）を切り替えたい場合:
#   make MAIN=merged_section5_final_clean
MAIN ?= main_up

TEX      := $(MAIN).tex
OUTDIR   ?= build
LATEXMK  ?= latexmk
LMKRC    ?= latexmkrc

# latexmkrc で
#   $latex = 'uplatex';
#   $dvipdf = 'dvipdfmx ...';
#   $bibtex = 'upbibtex';
# などが設定済みなので、ここではそれを使ってビルドします。
LATEXMKFLAGS := -pdfdvi -r $(LMKRC) -outdir=$(OUTDIR) \
	-interaction=nonstopmode -file-line-error -halt-on-error

PDF := $(OUTDIR)/$(MAIN).pdf

.PHONY: all pdf clean distclean watch help

all: pdf
pdf: $(PDF)

# 依存関係は「プロジェクト内の主要ファイルが更新されたら再ビルド」程度に広めに取っています
$(PDF): $(TEX) $(LMKRC) \
        $(wildcard *.tex) $(wildcard *.bib) \
        $(wildcard *.cls) $(wildcard *.sty) \
        $(wildcard images/*) $(wildcard figure/*) $(wildcard figures/*)
	@mkdir -p $(OUTDIR)
	$(LATEXMK) $(LATEXMKFLAGS) $(TEX)

# 常駐ビルド（保存のたびに自動コンパイル）
watch:
	@mkdir -p $(OUTDIR)
	$(LATEXMK) $(LATEXMKFLAGS) -pvc $(TEX)

# 中間生成物の掃除（latexmk管理分）
clean:
	$(LATEXMK) -C -r $(LMKRC) -outdir=$(OUTDIR) $(TEX)

# 出力ディレクトリごと削除
distclean: clean
	rm -rf $(OUTDIR)

help:
	@echo "Targets:"
	@echo "  make [MAIN=main_up]        Build PDF -> $(PDF)"
	@echo "  make watch [MAIN=...]      Watch mode (latexmk -pvc)"
	@echo "  make clean                 Remove aux files in $(OUTDIR)"
	@echo "  make distclean             Remove $(OUTDIR) entirely"
