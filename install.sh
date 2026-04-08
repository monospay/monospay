#!/usr/bin/env bash
# install.sh — mono M2M SDK  ·  Scorched-Earth Installer
#
# Garantiert: Keine alten Versionen, kein pip-Cache, kein pipx-Cache.
# Ablauf: nuke → fresh install → mono init
#
# Usage:
#   curl -fsSL https://monospay.com/install.sh | bash

set -euo pipefail

# ── ANSI ─────────────────────────────────────────────────────────────────────
R="\033[0m"; BOLD="\033[1m"; DIM="\033[2m"
GRN="\033[32m"; RED="\033[31m"; YLW="\033[33m"

ok()   { echo -e "  ${GRN}✓${R}  $*"; }
err()  { echo -e "  ${RED}✗${R}  $*" >&2; }
warn() { echo -e "  ${YLW}!${R}  $*"; }
dim()  { echo -e "  ${DIM}$*${R}"; }
rule() { printf "  ${DIM}"; printf '─%.0s' {1..56}; echo -e "${R}"; }

# ── Header ────────────────────────────────────────────────────────────────────
echo
echo -e "  ${BOLD}mono M2M SDK — Installer${R}"
rule
echo

# ── Python check (3.9+) ───────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
  err "Python 3.9+ is required but was not found."
  dim "Install from https://python.org and re-run."
  exit 1
fi

PY_MAJOR=$(python3 -c "import sys; print(sys.version_info.major)")
PY_MINOR=$(python3 -c "import sys; print(sys.version_info.minor)")
PY_VER="${PY_MAJOR}.${PY_MINOR}"

if [[ "$PY_MAJOR" -lt 3 || ( "$PY_MAJOR" -eq 3 && "$PY_MINOR" -lt 9 ) ]]; then
  err "Python ${PY_VER} found — 3.9+ required."
  exit 1
fi
ok "Python ${PY_VER}"

# ── Detect pip ────────────────────────────────────────────────────────────────
if   command -v pip3 &>/dev/null; then PIP=pip3
elif command -v pip  &>/dev/null; then PIP=pip
else
  err "pip not found. Install pip and re-run."
  exit 1
fi

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 1 — SCORCHED EARTH
# Remove every trace of the old SDK before touching anything new.
# `|| true` on every removal — script never aborts on a clean machine.
# ═══════════════════════════════════════════════════════════════════════════════
echo
echo -e "  ${BOLD}Phase 1 — Removing old versions${R}"
rule

# 1a. Remove pipx-installed version (isolated venv)
if command -v pipx &>/dev/null; then
  echo -n "  Uninstalling via pipx ..."
  if pipx uninstall mono-m2m-sdk 2>/dev/null; then
    echo -e "\r  ${GRN}✓${R}  pipx: old version removed              "
  else
    echo -e "\r  ${DIM}–  pipx: nothing to remove${R}               "
  fi
fi

# 1b. Remove pip global/user install (covers legacy installs and CI images)
echo -n "  Uninstalling via pip ..."
if "$PIP" uninstall mono-m2m-sdk -y 2>/dev/null; then
  echo -e "\r  ${GRN}✓${R}  pip: old version removed                "
else
  echo -e "\r  ${DIM}–  pip: nothing to remove${R}                  "
fi

# 1c. Nuke pip's wheel cache for this package specifically.
# Prevents --force-reinstall from silently using a cached .whl.
echo -n "  Purging pip cache ..."
"$PIP" cache remove mono_m2m_sdk 2>/dev/null || true
"$PIP" cache remove mono-m2m-sdk 2>/dev/null || true
echo -e "\r  ${GRN}✓${R}  pip cache purged                          "

# 1d. Remove any stale `mono` binary that pip may have left in PATH.
#     pipx installs to ~/.local/share/pipx/venvs and links to ~/.local/bin.
#     A global pip install also writes to ~/.local/bin and can shadow pipx.
for CANDIDATE in \
    "${HOME}/.local/bin/mono" \
    "$(python3 -m site --user-base 2>/dev/null)/bin/mono"
do
  if [[ -f "$CANDIDATE" ]]; then
    rm -f "$CANDIDATE" 2>/dev/null && \
      dim "Removed stale binary: ${CANDIDATE}" || true
  fi
done

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 2 — FRESH INSTALL FROM PyPI
# pipx preferred: gives the mono binary its own isolated Python environment.
# pip fallback: for environments where pipx is unavailable (CI, Docker, etc.).
# ═══════════════════════════════════════════════════════════════════════════════
echo
echo -e "  ${BOLD}Phase 2 — Installing latest version from PyPI${R}"
rule

if command -v pipx &>/dev/null; then
  dim "Using pipx (isolated environment) ..."
  echo
  # --force: always create a fresh venv, even if the name is still registered
  pipx install --force mono-m2m-sdk
  INSTALL_METHOD="pipx"
else
  warn "pipx not found — falling back to pip."
  warn "For isolation: pip install pipx && pipx install mono-m2m-sdk"
  echo
  # --force-reinstall: bypass locally cached wheels
  # --no-cache-dir:    bypass pip's HTTP cache (CDN-level)
  "$PIP" install \
    --upgrade \
    --force-reinstall \
    --no-cache-dir \
    mono-m2m-sdk
  INSTALL_METHOD="pip"
fi

echo

# ── Verify binary is on PATH ──────────────────────────────────────────────────
if ! command -v mono &>/dev/null; then
  echo
  warn "The 'mono' command is not in PATH yet."
  dim "Add this to your shell profile and restart your terminal:"
  echo
  echo -e "    ${BOLD}export PATH=\"\${HOME}/.local/bin:\${PATH}\"${R}"
  echo
  # Last resort: launch directly via absolute path (pipx installs here)
  PIPX_BIN="${HOME}/.local/bin/mono"
  if [[ "$INSTALL_METHOD" == "pipx" && -x "$PIPX_BIN" ]]; then
    dim "Launching directly: ${PIPX_BIN} ..."
    exec "$PIPX_BIN" init
  fi
  dim "Once PATH is set, run: mono init"
  exit 0
fi

INSTALLED_VER=$(mono --version 2>/dev/null \
  | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || echo "unknown")

ok "mono-m2m-sdk ${INSTALLED_VER} installed  (via ${INSTALL_METHOD})"
rule
echo

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 3 — HAND OFF TO CLI
# exec replaces this shell process entirely — no subprocess, no cleanup race.
# The user goes directly from install → auth → balance in one unbroken flow.
# ═══════════════════════════════════════════════════════════════════════════════
exec mono init
