#!/usr/bin/env bash
set -euo pipefail

# Release script: update versions, generate CHANGELOG, tag, and push.
# Usage: ./scripts/release.sh <VERSION>
# Example: ./scripts/release.sh 1.0.0

VERSION="${1:-}"

if [ -z "$VERSION" ]; then
  echo "Usage: $0 <VERSION>"
  echo "Example: $0 1.0.0"
  exit 1
fi

# Validate semver format
if ! echo "$VERSION" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+$'; then
  echo "Error: Version must be in semver format (X.Y.Z), got: $VERSION"
  exit 1
fi

# Check for clean working tree
if ! git diff --quiet HEAD 2>/dev/null; then
  echo "Error: Working tree is dirty. Commit or stash changes first."
  exit 1
fi

# Check tag doesn't already exist
if git rev-parse "v$VERSION" >/dev/null 2>&1; then
  echo "Error: Tag v$VERSION already exists."
  exit 1
fi

echo "Releasing v$VERSION..."

# --- Step 1: Update tauri.conf.json ---
TAURI_CONF="src-tauri/tauri.conf.json"
if [ -f "$TAURI_CONF" ]; then
  sed -i "s/\"version\": \"[^\"]*\"/\"version\": \"$VERSION\"/" "$TAURI_CONF"
  echo "Updated $TAURI_CONF"
fi

# --- Step 2: Update pyproject.toml ---
PYPROJECT="pyproject.toml"
if [ -f "$PYPROJECT" ]; then
  sed -i "s/^version = \"[^\"]*\"/version = \"$VERSION\"/" "$PYPROJECT"
  echo "Updated $PYPROJECT"
fi

# --- Step 3: Generate CHANGELOG entry ---
CHANGELOG="CHANGELOG.md"
PREV_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "")
DATE=$(date +%Y-%m-%d)

if [ -n "$PREV_TAG" ]; then
  RANGE="${PREV_TAG}..HEAD"
else
  RANGE="HEAD"
fi

# Collect commits by category
ADDED=""
FIXED=""
CHANGED=""
DOCS=""

while IFS= read -r line; do
  # Strip leading spaces and extract type + optional scope + description
  MSG=$(echo "$line" | sed 's/^[a-f0-9]* //')

  TYPE=$(echo "$MSG" | sed -n 's/^\([a-z]*\)\(([^)]*)\)\?: .*/\1/p')
  SCOPE=$(echo "$MSG" | sed -n 's/^[a-z]*(\([^)]*\)): .*/\1/p')
  DESC=$(echo "$MSG" | sed -n 's/^[a-z]*\(([^)]*)\)\?: \(.*\)/\2/p')

  [ -z "$DESC" ] && continue

  if [ -n "$SCOPE" ]; then
    ENTRY="- **${SCOPE}**: ${DESC}"
  else
    ENTRY="- ${DESC}"
  fi

  case "$TYPE" in
    feat)     ADDED="${ADDED}${ENTRY}\n" ;;
    fix)      FIXED="${FIXED}${ENTRY}\n" ;;
    update|refactor|perf) CHANGED="${CHANGED}${ENTRY}\n" ;;
    docs)     DOCS="${DOCS}${ENTRY}\n" ;;
    *)        ;; # chore, ci, test, style — skip
  esac
done < <(git log --oneline "$RANGE" 2>/dev/null)

# Build the new changelog section
SECTION="## [$VERSION] - $DATE\n"
[ -n "$ADDED" ]   && SECTION="${SECTION}\n### Added\n${ADDED}"
[ -n "$FIXED" ]   && SECTION="${SECTION}\n### Fixed\n${FIXED}"
[ -n "$CHANGED" ] && SECTION="${SECTION}\n### Changed\n${CHANGED}"
[ -n "$DOCS" ]    && SECTION="${SECTION}\n### Documentation\n${DOCS}"

# Prepend to CHANGELOG.md
if [ -f "$CHANGELOG" ]; then
  # Insert after the "# Changelog" header
  TEMP=$(mktemp)
  awk -v section="$(echo -e "$SECTION")" '
    /^# Changelog/ { print; print ""; print section; next }
    { print }
  ' "$CHANGELOG" > "$TEMP"
  mv "$TEMP" "$CHANGELOG"
else
  echo -e "# Changelog\n\n${SECTION}" > "$CHANGELOG"
fi

echo "Updated $CHANGELOG"

# --- Step 4: Commit, tag, push ---
git add "$TAURI_CONF" "$PYPROJECT" "$CHANGELOG"
git commit -m "chore(release): v$VERSION"
git tag "v$VERSION"

echo ""
echo "Release v$VERSION prepared. Run the following to publish:"
echo "  git push origin HEAD --tags"
