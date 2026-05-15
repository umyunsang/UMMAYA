#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKSPACE="$ROOT_DIR/docs/architecture/c4/workspace.dsl"
DOT_DIR="$ROOT_DIR/docs/architecture/c4/out/dot"
SVG_DIR="$ROOT_DIR/docs-site/public/architecture/c4"

mkdir -p "$DOT_DIR" "$SVG_DIR"

find "$DOT_DIR" -maxdepth 1 -name 'structurizr-*.dot' -delete
find "$SVG_DIR" -maxdepth 1 -name 'structurizr-*.svg' -delete

structurizr-cli validate -w "$WORKSPACE"
structurizr-cli export -w "$WORKSPACE" -f dot -o "$DOT_DIR"

for dot_file in "$DOT_DIR"/*.dot; do
  base="$(basename "$dot_file" .dot)"
  dot -Tsvg "$dot_file" -o "$SVG_DIR/$base.svg"
done

printf 'Rendered C4 diagrams to %s\n' "$SVG_DIR"
