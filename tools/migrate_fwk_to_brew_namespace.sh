#!/usr/bin/env bash
set -euo pipefail

# BrewAssistant v4 breaking namespace migration
#
# This script performs the broad migration from legacy fwk_* entities to brew_*
# entities in package YAML files and removes the transitional alias packages.
#
# Intended use:
#   1. Run from repository root
#   2. Review git diff carefully
#   3. Test in Home Assistant
#   4. Commit only if the diff is acceptable

ROOT_DIR="$(pwd)"
PACKAGES_DIR="$ROOT_DIR/packages"

if [[ ! -d "$PACKAGES_DIR" ]]; then
  echo "ERROR: packages directory not found. Run this from the repository root." >&2
  exit 1
fi

echo "== BrewAssistant v4: fwk_ -> brew_ namespace migration =="
echo

ALIAS_FILES=(
  "packages/brewassistant_namespace_aliases.yaml"
  "packages/brewassistant_namespace_aliases_main_card_helpers.yaml"
  "packages/brewassistant_namespace_aliases_notifications.yaml"
  "packages/brewassistant_namespace_aliases_fermentation.yaml"
  "packages/brewassistant_namespace_aliases_chamber.yaml"
)

TARGET_FILES=(
  "packages/brewassistant_notifications_module.yaml"
  "packages/brewassistant_chamber_module.yaml"
  "packages/brewassistant_fermentation_module.yaml"
  "packages/brewassistant_brewfather_adapter.yaml"
)

echo "Removing transitional alias files..."
for file in "${ALIAS_FILES[@]}"; do
  if [[ -f "$file" ]]; then
    rm "$file"
    echo "  removed $file"
  else
    echo "  skipped missing $file"
  fi
done

echo
echo "Renaming fwk_ -> brew_ in target package files..."
for file in "${TARGET_FILES[@]}"; do
  if [[ -f "$file" ]]; then
    perl -0pi -e 's/fwk_/brew_/g' "$file"
    echo "  migrated $file"
  else
    echo "  skipped missing $file"
  fi
done

echo
echo "Remaining fwk_ references in packages:"
if grep -R "fwk_" -n packages 2>/dev/null; then
  echo
  echo "WARNING: fwk_ references remain. Review whether they are expected docs/comments or missed files."
else
  echo "  none"
fi

echo
echo "Git status:"
git status --short

echo
echo "Done. Review with:"
echo "  git diff -- packages"
echo
echo "Suggested commit message:"
echo "  Breaking rename fwk namespace to brew"
