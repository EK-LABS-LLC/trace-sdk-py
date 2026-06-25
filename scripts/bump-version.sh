#!/usr/bin/env bash
set -euo pipefail

version="${1:-}"

if [[ ! "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Usage: make bump VERSION=x.y.z" >&2
  exit 2
fi

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

awk -v version="$version" '
  /^\[project\]$/ { in_project = 1; print; next }
  /^\[/ { in_project = 0 }
  in_project && /^version = / {
    print "version = \"" version "\""
    next
  }
  { print }
' pyproject.toml > "$tmp"
mv "$tmp" pyproject.toml

echo "Updated Python SDK version to $version."
