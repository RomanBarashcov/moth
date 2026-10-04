#!/usr/bin/env bash
# Usage:
#   collect-evidence.sh collect <before-output-dir> <after-output-dir> <dest-dir>
#   collect-evidence.sh publish <service-repo-dir> <dest-dir> <TICKET-ID> [branch]
#   collect-evidence.sh markdown <dest-dir> <base-url>
#
# collect:  copies one screenshot + the video of every Playwright test from the
#           before/after `--output` dirs into <dest-dir> as
#           <before|after>-<test>.{png,webm,gif}. GIFs need ffmpeg.
# publish:  commits <dest-dir> as <TICKET-ID>/ onto an orphan branch
#           (default `moth-evidence`, never merged) without touching the
#           working tree, pushes it and prints the commit-pinned base URL.
# markdown: prints a before/after table for the PR body from that base URL.
set -euo pipefail

slug() {
  local name
  name=$(basename "$1" | sed -E 's/-(chromium|firefox|webkit|Mobile-Chrome|Mobile-Safari)$//')
  if [[ $name =~ -[0-9a-f]{5}-(.*)$ ]]; then
    name=$(sed -E 's/^-*[^-]*-+//' <<<"${BASH_REMATCH[1]}")
  fi
  cut -c1-60 <<<"$name" | sed -E 's/-+$//'
}

pick_screenshot() {
  ls "$1"/test-finished-*.png 2>/dev/null | tail -1 ||
    ls "$1"/test-failed-*.png 2>/dev/null | tail -1 ||
    ls "$1"/*.png 2>/dev/null | tail -1
}

collect() {
  local before=$1 after=$2 dest=$3
  mkdir -p "$dest"
  for phase in before after; do
    local src=$before
    [ "$phase" = after ] && src=$after
    for dir in "$src"/*/; do
      [ -d "$dir" ] || continue
      local name png
      name=$(slug "$dir")
      png=$(pick_screenshot "$dir" || true)
      [ -n "$png" ] && cp "$png" "$dest/$phase-$name.png"
      if [ -f "$dir/video.webm" ]; then
        cp "$dir/video.webm" "$dest/$phase-$name.webm"
        if command -v ffmpeg >/dev/null; then
          ffmpeg -loglevel error -y -i "$dir/video.webm" \
            -vf "fps=8,scale=800:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=96[p];[b][p]paletteuse=dither=bayer" \
            "$dest/$phase-$name.gif"
        fi
      fi
    done
  done
  ls -1 "$dest"
}

markdown() {
  local dest=$1 base=$2
  echo "| | Before (base) | After (fix) |"
  echo "|---|---|---|"
  for png in "$dest"/after-*.png; do
    [ -f "$png" ] || continue
    local name=${png##*/after-}
    name=${name%.png}
    echo "| \`$name\` | ![before]($base/before-$name.png?raw=true) | ![after]($base/after-$name.png?raw=true) |"
    if [ -f "$dest/after-$name.gif" ]; then
      echo "| recording | ![before]($base/before-$name.gif?raw=true) | ![after]($base/after-$name.gif?raw=true) |"
    fi
  done
  echo
  local links=()
  for video in "$dest"/*.webm; do
    [ -f "$video" ] || continue
    local file=${video##*/}
    links+=("[${file%.webm}]($base/$file?raw=true)")
  done
  if [ ${#links[@]} -gt 0 ]; then
    local IFS='·'
    echo "Full videos: ${links[*]}"
  fi
}

publish() {
  local repo=$1 src=$2 ticket=$3 branch=${4:-moth-evidence}
  src=$(cd "$src" && pwd)
  cd "$repo"
  git fetch -q origin "$branch" 2>/dev/null || true
  local parent index slug commit
  parent=$(git rev-parse -q --verify "refs/remotes/origin/$branch" || true)
  index=$(mktemp)
  export GIT_INDEX_FILE=$index
  if [ -n "$parent" ]; then git read-tree "$parent"; else git read-tree --empty; fi
  git rm -r -q --cached --ignore-unmatch -- "$ticket" >/dev/null
  for file in "$src"/*; do
    [ -f "$file" ] || continue
    git update-index --add --cacheinfo "100644,$(git hash-object -w "$file"),$ticket/${file##*/}"
  done
  commit=$(git commit-tree "$(git write-tree)" ${parent:+-p "$parent"} -m "evidence: $ticket")
  unset GIT_INDEX_FILE
  rm -f "$index"
  git push -q origin "$commit:refs/heads/$branch"
  slug=$(gh repo view --json nameWithOwner -q .nameWithOwner)
  echo "https://github.com/$slug/blob/$commit/$ticket"
}

case "${1:-}" in
  collect) shift; collect "$@" ;;
  markdown) shift; markdown "$@" ;;
  publish) shift; publish "$@" ;;
  *) sed -n '2,16p' "$0"; exit 1 ;;
esac
