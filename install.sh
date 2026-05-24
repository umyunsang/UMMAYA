#!/bin/sh
# SPDX-License-Identifier: Apache-2.0

set -eu

tap="umyunsang/ummaya"
cask="ummaya"
cask_ref="$tap/$cask"
dry_run=0
target="stable"

usage() {
  cat <<'USAGE'
Install UMMAYA on macOS with the Homebrew cask.

Usage:
  curl -fsSL https://raw.githubusercontent.com/umyunsang/UMMAYA/main/install.sh | bash
  curl -fsSL https://raw.githubusercontent.com/umyunsang/UMMAYA/main/install.sh | bash -s -- --dry-run

Options:
  --dry-run   Print the Homebrew commands without running them.
  -h, --help  Show this help.

Targets:
  stable      Install or update the current tap cask. This is the default.
  latest      Alias for stable.
USAGE
}

log() {
  printf '%s\n' "$*"
}

fail() {
  printf 'install.sh: %s\n' "$*" >&2
  exit 1
}

run() {
  if [ "$dry_run" -eq 1 ]; then
    printf '+'
    for arg in "$@"; do
      printf ' %s' "$arg"
    done
    printf '\n'
    return 0
  fi
  "$@"
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run)
      dry_run=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    stable|latest)
      target="$1"
      ;;
    *)
      fail "unsupported argument '$1'; this installer only supports the Homebrew cask target"
      ;;
  esac
  shift
done

case "$target" in
  stable|latest) ;;
  *) fail "unsupported target '$target'" ;;
esac

case "$(uname -s)" in
  Darwin) ;;
  *)
    fail "this installer uses a Homebrew cask and currently supports macOS only. On this platform, use: npm install -g ummaya"
    ;;
esac

if ! command -v brew >/dev/null 2>&1; then
  fail "Homebrew is required. Install it from https://brew.sh, then rerun this script."
fi

log "Installing UMMAYA via Homebrew cask..."

if [ "$dry_run" -eq 1 ]; then
  run brew install --cask "$cask_ref"
  printf '+ %s\n' "verify $cask"
  exit 0
fi

if brew list --cask "$cask" >/dev/null 2>&1; then
  outdated="$(brew outdated --cask "$cask_ref" || true)"
  if [ -n "$outdated" ]; then
    run brew upgrade --cask "$cask_ref"
  elif [ -x "$(brew --prefix)/bin/ummaya" ] && "$(brew --prefix)/bin/ummaya" --version >/dev/null 2>&1; then
    log "UMMAYA is already installed and healthy."
  else
    run brew reinstall --cask "$cask_ref"
  fi
else
  run brew install --cask "$cask_ref"
fi

if [ "$dry_run" -eq 1 ]; then
  exit 0
fi

brew_prefix="$(brew --prefix)"
brew_bin="$brew_prefix/bin/ummaya"

if [ -x "$brew_bin" ]; then
  "$brew_bin" --version
  resolved="$(command -v ummaya || true)"
  if [ -n "$resolved" ] && [ "$resolved" != "$brew_bin" ]; then
    log "Homebrew installed UMMAYA at $brew_bin, but PATH resolves 'ummaya' to $resolved."
  fi
elif command -v ummaya >/dev/null 2>&1; then
  ummaya --version
  log "Add $brew_prefix/bin to PATH to run 'ummaya' directly."
else
  fail "UMMAYA installed, but the 'ummaya' command was not found on PATH."
fi
