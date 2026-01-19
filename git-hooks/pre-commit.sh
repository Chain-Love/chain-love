#!/usr/bin/env bash
set -euo pipefail

REMOTE="origin"
SOURCE_BRANCH="json-tools"
SOURCE_REF="$REMOTE/$SOURCE_BRANCH"

TMP_DIR="$(mktemp -d -t precommit-root-XXXXXX)"


COPY_FROM_BRANCH=(
  "tools/"
)

SCRIPTS=(
  "csv_to_json.py"
  "validate.py"
)

cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

# Ensure python3 is installed
command -v python3 >/dev/null 2>&1 || {
  echo "Error: python3 not found"
  exit 1
}

echo "Ensuring latest tools are fetched"
git fetch --quiet "$REMOTE" "$SOURCE_BRANCH"

echo "Creating temporary project copy"
git archive HEAD | tar -x -C "$TMP_DIR"

echo "Overlaying tools from '$SOURCE_BRANCH'"
for path in "${COPY_FROM_BRANCH[@]}"; do
  clean_path="${path%/}"
  strip_components="$(tr '/' '\n' <<< "$clean_path" | wc -l)"

  git show "$SOURCE_REF:$clean_path" >/dev/null 2>&1 || {
    echo "Error: '$path' not found in $SOURCE_REF"
    exit 1
  }

  git archive "$SOURCE_REF" "$path" \
    | tar -x -C "$TMP_DIR" --strip-components="$strip_components"
done

echo "Installing dependencies"
if [[ -f "$TMP_DIR/requirements.txt" ]]; then
  python3 -m venv "$TMP_DIR/.venv"
  source "$TMP_DIR/.venv/bin/activate"
  pip install \
    --quiet \
    --disable-pip-version-check \
    -r "$TMP_DIR/requirements.txt"
fi

echo "Running scripts in project root context"
pushd "$TMP_DIR" >/dev/null

for script in "${SCRIPTS[@]}"; do
  echo "  - python3 $script"
  python3 "$script"
done

popd >/dev/null

echo "Pre-commit checks passed"