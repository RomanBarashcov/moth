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
# markdown: prints a before/after table for the PR body from that base URL,
#           or a single "Now" column when <dest-dir> has no before-* files.
set -euo pipefail

USAGE_LINES='2,14p'
GIF_FILTER='fps=8,scale=800:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=96[p];[b][p]paletteuse=dither=bayer'
BROWSER_SUFFIX='-(chromium|firefox|webkit|Mobile-Chrome|Mobile-Safari)$'

test_name() {
  local name
  name=$(basename "$1" | sed -E "s/$BROWSER_SUFFIX//")
  if [[ $name =~ -[0-9a-f]{5}-(.*)$ ]]; then
    name=$(sed -E 's/^-*[^-]*-+//' <<<"${BASH_REMATCH[1]}")
  fi
  cut -c1-60 <<<"$name" | sed -E 's/-+$//'
}

pick_screenshot() {
  local pattern match
  for pattern in 'test-finished-*.png' 'test-failed-*.png' '*.png'; do
    match=$(find "$1" -maxdepth 1 -name "$pattern" | sort | tail -1)
    if [ -n "$match" ]; then
      echo "$match"
      return
    fi
  done
}

collect_phase() {
  local phase=$1 src=$2 dest=$3 dir name png
  for dir in "$src"/*/; do
    [ -d "$dir" ] || continue
    name="$phase-$(test_name "$dir")"
    png=$(pick_screenshot "$dir")
    [ -z "$png" ] || cp "$png" "$dest/$name.png"
    [ -f "$dir/video.webm" ] || continue
    cp "$dir/video.webm" "$dest/$name.webm"
    if command -v ffmpeg >/dev/null; then
      ffmpeg -loglevel error -y -i "$dir/video.webm" -vf "$GIF_FILTER" "$dest/$name.gif"
    fi
  done
}

collect() {
  local before=$1 after=$2 dest=$3
  mkdir -p "$dest"
  collect_phase before "$before" "$dest"
  collect_phase after "$after" "$dest"
  ls -1 "$dest"
}

markdown() {
  local dest=$1 base=$2 png name video
  local -a links=()
  url() { echo "$base/$1?raw=true"; }
  if compgen -G "$dest/before-*" >/dev/null; then
    row() { echo "| $1 | ![before]($(url "before-$2.$3")) | ![after]($(url "after-$2.$3")) |"; }
    echo "| | Before (base) | After (fix) |"
    echo "|---|---|---|"
  else
    row() { echo "| $1 | ![now]($(url "after-$2.$3")) |"; }
    echo "| | Now |"
    echo "|---|---|"
  fi
  for png in "$dest"/after-*.png; do
    [ -f "$png" ] || continue
    name=${png##*/after-}
    name=${name%.png}
    row "\`$name\`" "$name" png
    [ ! -f "$dest/after-$name.gif" ] || row recording "$name" gif
  done

  for video in "$dest"/*.webm; do
    [ -f "$video" ] || continue
    video=${video##*/}
    links+=("[${video%.webm}]($(url "$video"))")
  done
  if [ ${#links[@]} -gt 0 ]; then
    echo
    (IFS='·'; echo "Full videos: ${links[*]}")
  fi
}

publish() {
  local repo=$1 src=$2 ticket=$3 branch=${4:-moth-evidence}
  local parent commit file index repo_name
  src=$(cd "$src" && pwd)
  cd "$repo"
  git fetch -q origin "$branch" 2>/dev/null || true
  parent=$(git rev-parse -q --verify "refs/remotes/origin/$branch" || true)

  index=$(mktemp)
  trap 'rm -f "$index"' RETURN
  export GIT_INDEX_FILE=$index
  if [ -n "$parent" ]; then git read-tree "$parent"; else git read-tree --empty; fi
  git rm -r -q --cached --ignore-unmatch -- "$ticket" >/dev/null
  for file in "$src"/*; do
    [ -f "$file" ] || continue
    git update-index --add --cacheinfo "100644,$(git hash-object -w "$file"),$ticket/${file##*/}"
  done
  commit=$(git commit-tree "$(git write-tree)" ${parent:+-p "$parent"} -m "evidence: $ticket")
  unset GIT_INDEX_FILE

  git push -q origin "$commit:refs/heads/$branch"
  repo_name=$(gh repo view --json nameWithOwner -q .nameWithOwner)
  echo "https://github.com/$repo_name/blob/$commit/$ticket"
}

case "${1:-}" in
  collect) shift; collect "$@" ;;
  markdown) shift; markdown "$@" ;;
  publish) shift; publish "$@" ;;
  *) sed -n "$USAGE_LINES" "$0"; exit 1 ;;
esac
