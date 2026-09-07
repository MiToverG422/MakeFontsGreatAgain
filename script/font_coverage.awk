# Selectively turn OEM text families into aliases of MFGA's sans-serif.
# Parse balanced XML tokens, not lines: family-list contains nested families.
# Reject unsupported/malformed input before emitting anything. No DTD/entities.
function fail() {
    print "MFGA: unsupported or malformed customization XML near offset " pos > "/dev/stderr"
    bad = 1; exit 2
}
function attr(tag, key,    rest, k, q, v) {
    rest = tag
    sub(/^<[^[:space:]>\/]+/, "", rest)
    while (rest !~ /^[[:space:]]*\/?[>]$/) {
        sub(/^[[:space:]]+/, "", rest)
        if (!match(rest, /^[A-Za-z_:][A-Za-z0-9_.:-]*/)) fail()
        k = substr(rest, 1, RLENGTH); rest = substr(rest, RLENGTH + 1)
        sub(/^[[:space:]]*=[[:space:]]*/, "", rest)
        q = substr(rest, 1, 1)
        if (q != "\"" && q != "\047") fail()
        rest = substr(rest, 2)
        if (!index(rest, q)) fail()
        v = substr(rest, 1, index(rest, q) - 1)
        rest = substr(rest, index(rest, q) + 1)
        if (k == key) return v
    }
    return ""
}
function targeted(name) {
    return name ~ /^google-sans(-(flex|text|medium|bold))?$/ ||
        name ~ /^variable-(body|title|headline|label|display)-(small|medium|large)(-emphasized)?$/
}
function weightOf(block,    rest, tag, w, best, distance) {
    best = 400; distance = 1000001; rest = block
    while (match(rest, /<font[[:space:]][^>]*>/)) {
        tag = substr(rest, RSTART, RLENGTH)
        rest = substr(rest, RSTART + RLENGTH)
        if (attr(tag, "style") == "italic") continue
        w = attr(tag, "weight"); if (w == "") w = 400
        if (w !~ /^[0-9]+$/ || w + 0 < 1 || w + 0 > 1000) fail()
        if ((w - 400)^2 < distance) { best = w; distance = (w - 400)^2 }
    }
    return best
}
{ xml = xml $0 "\n" }
END {
    if (bad) exit 2
    # Tokenize tags with quoted attributes, comments, and processing instructions.
    pos = 1; depth = 0; count = 0; start = 1
    while (pos <= length(xml)) {
        if (substr(xml, pos, 1) != "<") { pos++; continue }
        tail = substr(xml, pos)
        if (substr(tail, 1, 4) == "<!--") {
            n = index(tail, "-->"); if (!n) fail()
            pos += n + 2; continue
        }
        if (substr(tail, 1, 2) == "<?") {
            n = index(tail, "?>"); if (!n) fail()
            pos += n + 1; continue
        }
        if (substr(tail, 1, 2) == "<!") fail()
        q = ""; end = pos + 1
        for (; end <= length(xml); end++) {
            c = substr(xml, end, 1)
            if (q != "") { if (c == q) q = "" }
            else if (c == "\"" || c == "\047") q = c
            else if (c == ">") break
        }
        if (end > length(xml)) fail()
        tag = substr(xml, pos, end - pos + 1)
        closing = tag ~ /^<\//; empty = tag ~ /\/>$/
        name = tag; sub(/^<\/?/, "", name); sub(/[[:space:]\/ >].*$/, "", name)
        if (closing) {
            if (depth < 1 || stack[depth] != name) fail()
            depth--
            if (depth == 1) {
                blocks[count] = substr(xml, start, end - start + 1)
                start = end + 1
            } else if (depth == 0) {
                suffix = substr(xml, start); rootClosed = 1
            }
        } else {
            if (rootClosed) fail()
            if (depth == 0) {
                if (name != "fonts-modification" || empty) fail()
                prefix = substr(xml, 1, end); start = end + 1
            } else if (depth == 1) {
                count++; tags[count] = tag; kinds[count] = name
                names[count] = attr(tag, "name")
                leading[count] = substr(xml, start, pos - start)
                if (empty) { blocks[count] = substr(xml, start, end - start + 1); start = end + 1 }
            }
            if (!empty) { depth++; stack[depth] = name }
        }
        pos = end + 1
    }
    if (depth || !rootClosed) fail()
    for (i = 1; i <= count; i++) {
        if ((kinds[i] == "family" || kinds[i] == "family-list") && targeted(names[i]) &&
                attr(tags[i], "customizationType") == "new-named-family") {
            remap[names[i]] = 1; replace[i] = 1
            weights[i] = weightOf(blocks[i]); changed++
        }
        # Reinstalling reads the currently mounted XML, which may already use
        # our aliases. Copy them forward into the incoming module as well.
        if (kinds[i] == "alias" && targeted(names[i]) && attr(tags[i], "to") == "sans-serif") {
            remap[names[i]] = 1; replace[i] = 1; changed++
            weights[i] = attr(tags[i], "weight")
            if (weights[i] == "") weights[i] = 400
        }
    }
    # Android drops aliases whose targets are aliases, so flatten dependants too.
    for (pass = 1; pass <= count; pass++) {
        more = 0
        for (i = 1; i <= count; i++) {
            if (kinds[i] == "alias" && !replace[i] && remap[attr(tags[i], "to")]) {
                replace[i] = 1; remap[names[i]] = 1; more++; changed++
                weights[i] = attr(tags[i], "weight")
                if (weights[i] == "") weights[i] = 400
            }
        }
        if (!more) break
    }
    if (!changed) exit 3
    printf "%s", prefix
    for (i = 1; i <= count; i++) {
        if (replace[i]) {
            if (names[i] !~ /^[a-zA-Z0-9_-]+$/ || weights[i] !~ /^[0-9]+$/) fail()
            printf "%s<alias name=\"%s\" to=\"sans-serif\" weight=\"%s\"/>", leading[i], names[i], weights[i]
        } else printf "%s", blocks[i]
    }
    printf "%s", suffix
}
