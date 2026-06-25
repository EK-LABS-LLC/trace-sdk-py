#!/usr/bin/env bash
set -euo pipefail

version_from_pyproject() {
  awk '
    /^\[project\]$/ { in_project = 1; next }
    /^\[/ { in_project = 0 }
    in_project && /^version = / { gsub(/"/, "", $3); print $3; exit }
  ' "$1"
}

version_gt() {
  local current="$1"
  local base="$2"
  local current_major current_minor current_patch
  local base_major base_minor base_patch

  IFS=. read -r current_major current_minor current_patch <<< "$current"
  IFS=. read -r base_major base_minor base_patch <<< "$base"

  for part in "$current_major" "$current_minor" "$current_patch" "$base_major" "$base_minor" "$base_patch"; do
    if [[ ! "$part" =~ ^[0-9]+$ ]]; then
      echo "::error::Expected semantic versions in X.Y.Z format; got current=$current base=$base." >&2
      exit 1
    fi
  done

  if (( 10#$current_major != 10#$base_major )); then
    (( 10#$current_major > 10#$base_major ))
    return
  fi

  if (( 10#$current_minor != 10#$base_minor )); then
    (( 10#$current_minor > 10#$base_minor ))
    return
  fi

  (( 10#$current_patch > 10#$base_patch ))
}

base_ref="${BASE_REF:-origin/${GITHUB_BASE_REF:-main}}"
current_version="$(version_from_pyproject pyproject.toml)"
base_pyproject="$(mktemp)"
trap 'rm -f "$base_pyproject"' EXIT

git show "$base_ref:pyproject.toml" > "$base_pyproject"
base_version="$(version_from_pyproject "$base_pyproject")"

if ! version_gt "$current_version" "$base_version"; then
  echo "::error::Python SDK version must be bumped above $base_version before merging this PR. Current version is $current_version." >&2
  exit 1
fi

echo "Python SDK version bump OK: $base_version -> $current_version."
