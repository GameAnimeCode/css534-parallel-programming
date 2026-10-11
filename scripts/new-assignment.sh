#!/usr/bin/env bash
# Create assignments/<name>/ from the templates.
# Usage: scripts/new-assignment.sh a1-multithreading [cpp|java]
#        The language defaults to cpp.
set -euo pipefail
cd "$(dirname "$0")/.."

name="${1:?usage: $0 <assignment-name> [cpp|java]}"
lang="${2:-cpp}"
dest="assignments/$name"

if [[ "$lang" != "cpp" && "$lang" != "java" ]]; then
  echo "error: language must be cpp or java, got '$lang'" >&2
  exit 1
fi

if [[ -e "$dest" ]]; then
  echo "error: $dest already exists" >&2
  exit 1
fi

# Rewrite the list between the markers in README.md from the assignment folders.
update_readme() {
  local readme="README.md" start="<!-- assignments:start -->" end="<!-- assignments:end -->"
  if ! grep -qF "$start" "$readme" || ! grep -qF "$end" "$readme"; then
    echo "warning: assignment markers not found in $readme, skipping index update" >&2
    return
  fi
  local list
  list="$(mktemp)"
  find assignments -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort -V \
    | sed 's|.*|- [&](assignments/&)|' > "$list"
  awk -v s="$start" -v e="$end" -v f="$list" '
    $0 == s { print; while ((getline line < f) > 0) print line; skip = 1; next }
    $0 == e { skip = 0 }
    !skip   { print }' "$readme" > "$readme.tmp"
  mv "$readme.tmp" "$readme"
  rm -f "$list"
}

mkdir -p "$dest/src"
cp templates/writeup/writeup.qmd templates/writeup/preamble.tex "$dest/"
if [[ "$lang" == "cpp" ]]; then
  cp templates/code/cpp/main.cpp "$dest/src/"
  cp templates/code/cpp/Makefile "$dest/src/"
else
  cp templates/code/java/Main.java "$dest/src/"
fi

update_readme

echo "Created $dest ($lang)"
