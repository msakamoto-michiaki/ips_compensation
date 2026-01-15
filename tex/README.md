# TeX (Docker/CI) template with TeX Live + HaranoAji + latexmk

## What this gives you
- Deterministic builds in Linux containers (no macOS Hiragino required)
- ./fonts/ populated from TeX Live (HaranoAji) so fontspec can use Path=fonts/
- Makefile targets:
  - make fonts
  - make pdf
  - make clean / make distclean

## Quick start
make -f makefile.system clean
make -f makefile.system pdf MAIN=main.tex

make -f makefile.local distclean  #clean-up ./fonts/*
make -f makefile.local pdf MAIN=main.tex FONTSET=harano

make -f makefile.local distclean
make -f makefile.local pdf MAIN=main.tex FONTSET=noto


```

## Notes
- HaranoAji fonts are typically available when you install TeX Live Japanese collections
  (e.g., tlmgr install collection-langjapanese). If make fonts fails, add the relevant tlmgr packages.
