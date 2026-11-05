#!/bin/sh
set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
dist_dir="$repo_root/dist"
stage_dir=$(mktemp -d "${TMPDIR:-/tmp}/abstention-eval-submission.XXXXXX")
archive="$dist_dir/abstention-eval-submission.zip"

cleanup() {
    rm -rf "$stage_dir"
}
trap cleanup EXIT HUP INT TERM

if [ -e "$repo_root/.env" ] || [ -e "$repo_root/.env.local" ]; then
    echo "Refusing to package a local environment file." >&2
    exit 1
fi

mkdir -p "$dist_dir"
rm -f "$archive"
mkdir -p "$stage_dir/src" "$stage_dir/items" "$stage_dir/results" "$stage_dir/tests"

cp "$repo_root/README.md" "$stage_dir/README.md"
cp "$repo_root/DESIGN_DECISIONS.md" "$stage_dir/DESIGN_DECISIONS.md"
cp "$repo_root/LICENSE" "$stage_dir/LICENSE"
cp "$repo_root/pyproject.toml" "$stage_dir/pyproject.toml"
cp "$repo_root/uv.lock" "$stage_dir/uv.lock"
cp "$repo_root/.env.example" "$stage_dir/.env.example"
cp "$repo_root/VIDEO_WALKTHROUGH.md" "$stage_dir/VIDEO_WALKTHROUGH.md"
cp -R "$repo_root/src/." "$stage_dir/src/"
cp -R "$repo_root/items/." "$stage_dir/items/"
cp -R "$repo_root/tests/." "$stage_dir/tests/"
cp "$repo_root/results/published/full.csv" "$stage_dir/results/full.csv"

find "$stage_dir" -type d \( -name '__pycache__' -o -name '*.egg-info' \) \
    -prune -exec rm -rf {} +

if find "$stage_dir" -type f \( -name '.env' -o -name '.env.local' -o -name '*.key' \) | grep -q .; then
    echo "Refusing to package a credential-like file." >&2
    exit 1
fi

(cd "$stage_dir" && zip -qr "$archive" .)

archive_kb=$(du -k "$archive" | awk '{print $1}')
if [ "$archive_kb" -gt 51200 ]; then
    echo "Refusing to create an archive larger than 50 MB: ${archive_kb} KB" >&2
    rm -f "$archive"
    exit 1
fi

echo "Created: $archive"
echo "Size: ${archive_kb} KB"
unzip -l "$archive"
