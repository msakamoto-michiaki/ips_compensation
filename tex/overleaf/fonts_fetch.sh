#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FONTS_DIR="${ROOT_DIR}/fonts"
LIC_DIR="${FONTS_DIR}/LICENSES"

mkdir -p "${FONTS_DIR}" "${LIC_DIR}"

echo "==> Fetching Libertinus (Latin + Math) from GitHub releases..."
# Libertinus: GitHub releases provide OTF/TTF; pick latest tag manually or pin a version.
# You can pin versions for reproducibility:
LIBERTINUS_VER="7.040"  # update if needed
LIBERTINUS_ZIP="Libertinus-${LIBERTINUS_VER}.zip"
LIBERTINUS_URL="https://github.com/alerque/libertinus/releases/download/v${LIBERTINUS_VER}/${LIBERTINUS_ZIP}"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

curl -L -o "${tmp}/${LIBERTINUS_ZIP}" "${LIBERTINUS_URL}"
unzip -q "${tmp}/${LIBERTINUS_ZIP}" -d "${tmp}/libertinus"

# Find fonts (paths may vary per release)
# Copy minimal set you need:
#   LibertinusSerif-Regular/Bold/Italic/BoldItalic
#   LibertinusMath-Regular
#   (optional) LibertinusMono-Regular
find "${tmp}/libertinus" -type f -name "*.otf" > "${tmp}/otf_list.txt" || true

# Helper: copy if exists
copy_one() {
  local pattern="$1"  # e.g. "LibertinusSerif-Regular.otf"
  local dst="$2"
  local src
  src="$(grep -F "/${pattern}" "${tmp}/otf_list.txt" | head -n 1 || true)"
  if [[ -z "${src}" ]]; then
    echo "ERROR: cannot find ${pattern} in Libertinus package"
    exit 1
  fi
  cp -f "${src}" "${dst}"
}

copy_one "LibertinusSerif-Regular.otf"     "${FONTS_DIR}/LibertinusSerif-Regular.otf"
copy_one "LibertinusSerif-Bold.otf"        "${FONTS_DIR}/LibertinusSerif-Bold.otf"
copy_one "LibertinusSerif-Italic.otf"      "${FONTS_DIR}/LibertinusSerif-Italic.otf"
copy_one "LibertinusSerif-BoldItalic.otf"  "${FONTS_DIR}/LibertinusSerif-BoldItalic.otf"
copy_one "LibertinusMath-Regular.otf"      "${FONTS_DIR}/LibertinusMath-Regular.otf"

# Optional mono (uncomment if you want)
# copy_one "LibertinusMono-Regular.otf"    "${FONTS_DIR}/LibertinusMono-Regular.otf"

# License
# Libertinus license is OFL; include it.
lic_src="$(find "${tmp}/libertinus" -maxdepth 3 -type f \( -iname "OFL.txt" -o -iname "LICENSE*" \) | head -n 1 || true)"
if [[ -n "${lic_src}" ]]; then
  cp -f "${lic_src}" "${LIC_DIR}/LICENSE-Libertinus.txt"
else
  echo "WARN: Libertinus license file not found in zip; please add manually."
fi

echo "==> Fetching Noto Serif CJK JP..."
# Noto CJK is big. Use Google's official Noto CJK repo (OTF).
# Pin a commit for reproducibility:
NOTO_CJK_REPO="https://github.com/googlefonts/noto-cjk.git"
NOTO_DIR="${tmp}/noto-cjk"
git clone --depth 1 "${NOTO_CJK_REPO}" "${NOTO_DIR}"

# Copy JP serif regular/bold from repo (paths may change; these are typical)
# Search robustly:
noto_reg="$(find "${NOTO_DIR}" -type f -name "NotoSerifCJKjp-Regular.otf" | head -n 1 || true)"
noto_bold="$(find "${NOTO_DIR}" -type f -name "NotoSerifCJKjp-Bold.otf" | head -n 1 || true)"

if [[ -z "${noto_reg}" || -z "${noto_bold}" ]]; then
  echo "ERROR: Could not find NotoSerifCJKjp-Regular/Bold.otf in noto-cjk repo."
  echo "       The repo layout may have changed. Search manually under ${NOTO_DIR}."
  exit 1
fi

cp -f "${noto_reg}"  "${FONTS_DIR}/NotoSerifCJKjp-Regular.otf"
cp -f "${noto_bold}" "${FONTS_DIR}/NotoSerifCJKjp-Bold.otf"

# License (OFL)
noto_lic="$(find "${NOTO_DIR}" -maxdepth 3 -type f \( -iname "OFL.txt" -o -iname "LICENSE*" \) | head -n 1 || true)"
if [[ -n "${noto_lic}" ]]; then
  cp -f "${noto_lic}" "${LIC_DIR}/LICENSE-NotoCJK.txt"
else
  echo "WARN: Noto license file not found; please add manually."
fi

echo "==> Done. Fonts installed to: ${FONTS_DIR}"
echo "    - LibertinusSerif-*.otf"
echo "    - LibertinusMath-Regular.otf"
echo "    - NotoSerifCJKjp-*.otf"

