#!/usr/bin/env bash
# Render a writeup to PDF with Quarto, injecting personal details from
# .local/student.env (gitignored) so they never appear in committed files.
# Usage: scripts/build-writeup.sh a1-multithreading
#        scripts/build-writeup.sh            (renders every assignment)
set -euo pipefail
cd "$(dirname "$0")/.."

env_file=".local/student.env"
if [[ -f "$env_file" ]]; then
  # shellcheck disable=SC1090
  source "$env_file"
else
  echo "warning: $env_file not found, building with placeholder details" >&2
fi

# Escape characters that are special in LaTeX.
tex() { printf '%s' "$1" | sed 's/[&%$#_{}]/\\&/g'; }

build() {
  local dir
  dir="$(dirname "$1")"
  if [[ -f "$env_file" ]]; then
    {
      printf '\\newcommand{\\stuName}{%s}\n' "$(tex "${STUDENT_NAME:-First Last}")"
      printf '\\newcommand{\\stuLast}{%s}\n' "$(tex "${STUDENT_LAST:-Last}")"
      printf '\\newcommand{\\stuId}{%s}\n' "$(tex "${STUDENT_ID:-000000000}")"
      printf '\\newcommand{\\stuEmail}{%s}\n' "$(tex "${STUDENT_EMAIL:-netid@uw.edu}")"
    } > "$dir/personal.tex"
    trap 'rm -f "$dir/personal.tex"' RETURN
  fi
  quarto render "$1" --to pdf
}

if [[ $# -gt 0 ]]; then
  build "assignments/$1/writeup.qmd"
else
  for f in assignments/*/writeup.qmd; do
    [[ -e "$f" ]] && build "$f"
  done
fi
