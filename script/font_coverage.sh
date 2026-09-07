#!/system/bin/sh
# Return 0 when written, 3 for no matching families, 1 on failure.
mfga_prepare_font_customization() {
  local source="$1" dest="$2" parser="$3" tmp status
  [ -r "$source" ] && [ -r "$parser" ] || return 1
  mkdir -p "$(dirname "$dest")" || return 1
  tmp=$(mktemp "$dest.coverage.XXXXXX") || return 1
  awk -f "$parser" "$source" > "$tmp"
  status=$?
  if [ "$status" -eq 0 ]; then
    chmod 0644 "$tmp" && mv -f "$tmp" "$dest" && return 0
    status=1
  fi
  rm -f "$tmp"
  [ "$status" -eq 3 ] && return 3
  return 1
}
