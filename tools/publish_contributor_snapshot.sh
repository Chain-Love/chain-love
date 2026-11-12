#!/usr/bin/env bash
set -euo pipefail

source_sha=$1
snapshot_dir=$2
snapshot_script="$(dirname "$0")/contributor_snapshot.py"
python3 "$snapshot_script" verify --source-sha "$source_sha" --output "$snapshot_dir"

version=$(jq -er '.generatorVersion' "$snapshot_dir/manifest.json")
tag="contributor-v${version}-${source_sha}"
tag_ref="refs/tags/$tag"
repo_url="${GITHUB_SERVER_URL:?}/${GH_REPO:?}.git"
scratch_dir=$(mktemp -d)
trap 'rm -rf "$scratch_dir"' EXIT

resolve_tag() {
  git ls-remote "$repo_url" "$tag_ref" "$tag_ref^{}" |
    awk -v ref="$tag_ref" '$2 == ref { sha = $1 } $2 == ref "^{}" { peeled = $1 } END { print (peeled ? peeled : sha) }'
}

remote_sha=$(resolve_tag)
if [[ -n "$remote_sha" && "$remote_sha" != "$source_sha" ]]; then
  echo "Tag $tag already points to $remote_sha, expected $source_sha" >&2
  exit 1
fi

if release=$(gh release view "$tag" --json isDraft,targetCommitish 2>"$scratch_dir/view-error"); then
  is_draft=$(jq -er '.isDraft | booleans | tostring' <<<"$release")
  if [[ "$is_draft" == false ]]; then
    if [[ "$remote_sha" != "$source_sha" ]]; then
      echo "Published release $tag is missing the expected Git tag" >&2
      exit 1
    fi
    gh release download "$tag" --dir "$scratch_dir/assets"
    python3 "$snapshot_script" verify --source-sha "$source_sha" --output "$scratch_dir/assets"
    echo "Published snapshot $tag already verified"
    exit 0
  fi
  if ! jq -e --arg sha "$source_sha" '.targetCommitish == $sha' <<<"$release" >/dev/null; then
    echo "Draft release $tag targets a different commit" >&2
    exit 1
  fi
else
  if [[ $(cat "$scratch_dir/view-error") != "release not found" ]]; then
    cat "$scratch_dir/view-error" >&2
    exit 1
  fi
  gh release create "$tag" --target "$source_sha" --draft --latest=false \
    --title "Contributor snapshot for $source_sha" --notes "Source commit: $source_sha"
fi

# Only an unpublished draft can reach this step. A rerun can repair a partial upload.
gh release upload "$tag" --clobber "$snapshot_dir/contributor-index.json" \
  "$snapshot_dir/contributor-sources.tar.gz" "$snapshot_dir/manifest.json"
gh release download "$tag" --dir "$scratch_dir/assets"
python3 "$snapshot_script" verify --source-sha "$source_sha" --output "$scratch_dir/assets"
gh release edit "$tag" --target "$source_sha" --draft=false --latest=false

if [[ $(resolve_tag) != "$source_sha" ]]; then
  echo "Published tag $tag does not resolve to $source_sha" >&2
  exit 1
fi
