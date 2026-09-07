#!/system/bin/sh
# Sourced by customize.sh before fonts.xml is copied to the mount directories.
# These six standalone SFNT fonts vary between ROMs: *-Regular.ttf can be
# variable while *-Bold.ttf is static. See docs/font-variation-compat.md.

mfga_supports_bold_axis() {
  local font="$1" size tables table offset length
  [ -r "$font" ] || return 1
  size=$(wc -c < "$font") || return 1
  set -- $(od -An -v -tu1 -N 12 "$font" 2>/dev/null)
  [ "$#" -eq 12 ] || return 1
  case "$1:$2:$3:$4" in
    0:1:0:0|79:84:84:79) ;; # TrueType or OpenType/CFF; not a TTC.
    *) return 1 ;;
  esac
  tables=$(($5 * 256 + $6))
  [ "$tables" -gt 0 ] && [ $((12 + tables * 16)) -le "$size" ] || return 1
  table=$(od -An -v -tu1 -j 12 -N "$((tables * 16))" "$font" 2>/dev/null |
    awk -v count="$tables" '
      { for (i = 1; i <= NF; i++) bytes[n++] = $i }
      function u32(p) {
        return ((bytes[p] * 256 + bytes[p+1]) * 256 + bytes[p+2]) * 256 + bytes[p+3]
      }
      END {
        if (n != count * 16) exit 1
        for (p = 0; p < n; p += 16) {
          if (bytes[p] == 102 && bytes[p+1] == 118 && bytes[p+2] == 97 && bytes[p+3] == 114) {
            printf "%.0f %.0f\n", u32(p+8), u32(p+12)
            exit 0
          }
        }
        exit 1
      }') || return 1
  set -- $table
  [ "$#" -eq 2 ] || return 1
  offset="$1"
  length="$2"
  [ "$offset" -ge $((12 + tables * 16)) ] && [ "$length" -ge 16 ] &&
    [ $((offset + length)) -le "$size" ] || return 1
  od -An -v -tu1 -j "$offset" -N "$length" "$font" 2>/dev/null |
    awk -v table_length="$length" '
      { for (i = 1; i <= NF; i++) bytes[n++] = $i }
      function u16(p) { return bytes[p] * 256 + bytes[p+1] }
      function fixed(p, value) {
        value = ((bytes[p] * 256 + bytes[p+1]) * 256 + bytes[p+2]) * 256 + bytes[p+3]
        if (value >= 2147483648) value -= 4294967296
        return value / 65536
      }
      END {
        if (n != table_length || u16(0) != 1 || u16(2) != 0) exit 1
        start = u16(4); count = u16(8); stride = u16(10)
        if (start < 16 || stride < 20 || start + count * stride > n) exit 1
        for (i = 0; i < count; i++) {
          p = start + i * stride
          if (bytes[p] == 119 && bytes[p+1] == 103 && bytes[p+2] == 104 && bytes[p+3] == 116) {
            low = fixed(p+4); normal = fixed(p+8); high = fixed(p+12)
            if (low <= normal && normal <= high && low <= 700 && high >= 700) exit 0
            exit 1
          }
        }
        exit 1
      }'
}

mfga_prepare_font_config() {
  local xml="$1" module_fonts="$2" system_fonts="$3" tmp prefix regular replacement
  [ -f "$xml" ] || return 1
  tmp=$(mktemp "$xml.compat.XXXXXX") || return 1
  cp "$xml" "$tmp" || { rm -f "$tmp"; return 1; }
  for prefix in NotoSerifHebrew NotoSerifThai NotoSansGujarati NotoSansOriya NotoSansLao NotoSerifLao; do
    regular="$system_fonts/$prefix-Regular.ttf"
    # The incoming module takes precedence over the currently mounted system.
    [ ! -e "$module_fonts/$prefix-Regular.ttf" ] || regular="$module_fonts/$prefix-Regular.ttf"
    replacement="$prefix-Bold.ttf"
    if mfga_supports_bold_axis "$regular"; then
      replacement="$prefix-Regular.ttf<axis tag=\"wght\" stylevalue=\"700\"/>"
    fi
    # Match only the six known weight-700 entries; preserve fallbackFor/style.
    # Accept both forms so repeated runs and static-ROM installs are safe.
    sed -i \
      -e "s@\(<font[^>]*weight=\"700\"[^>]*>\)$prefix-Bold.ttf</font>@\1$replacement</font>@g" \
      -e "s@\(<font[^>]*weight=\"700\"[^>]*>\)$prefix-Regular.ttf<axis tag=\"wght\" stylevalue=\"700\"/></font>@\1$replacement</font>@g" \
      "$tmp" || { rm -f "$tmp"; return 1; }
  done
  cat "$tmp" > "$xml" || { rm -f "$tmp"; return 1; }
  rm -f "$tmp"
}
