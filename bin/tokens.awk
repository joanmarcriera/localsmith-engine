#!/usr/bin/awk -f
# tokens.awk — roll up logs/tokens.jsonl by day + provider.
#
# Usage:
#   awk -f bin/tokens.awk logs/tokens.jsonl
#   bin/ai zai "hi" ; awk -f bin/tokens.awk logs/tokens.jsonl
#
# Output columns: date  provider  calls  in_tok  out_tok  usd  sec
#
# Standards: pure POSIX awk, no jq. Parses one flat JSON object per line,
# which is the exact shape bin/ai writes. Will misbehave on pretty-printed
# JSON or nested objects — keep the log flat.

# Extract a top-level field value from one JSON line.
# Numbers come back as numbers, strings unquoted.
function field(line, key,   re, rest) {
    re = "\"" key "\":[ ]*"
    if (match(line, re)) {
        rest = substr(line, RSTART + RLENGTH)
        # number, including scientific notation (e.g. 6.9e-05)
        if (match(rest, /^-?[0-9]+(\.[0-9]+)?([eE][-+]?[0-9]+)?/))
            return substr(rest, 1, RLENGTH) + 0
        if (match(rest, /^"[^"]*"/))
            return substr(rest, 2, RLENGTH - 2)
    }
    return ""
}

{
    day = substr(field($0, "ts"), 1, 10)
    p   = field($0, "provider")
    if (day == "" || p == "") next            # skip malformed lines

    k = day SUBSEP p
    calls[k]++
    tin[k]  += field($0, "in")
    tout[k] += field($0, "out")
    usd[k]  += field($0, "usd")
    sec[k]  += field($0, "sec")
    keys[k]  = 1
}

END {
    printf "%-10s  %-9s  %5s  %8s  %8s  %8s  %8s\n", \
        "date", "provider", "calls", "in_tok", "out_tok", "usd", "sec"
    n = 0
    for (k in keys) ks[++n] = k
    # naive sort by key (date+provider) — adequate for human inspection
    for (i = 1; i <= n; i++)
        for (j = i + 1; j <= n; j++)
            if (ks[i] > ks[j]) { t = ks[i]; ks[i] = ks[j]; ks[j] = t }

    grand_in = grand_out = grand_usd = grand_sec = grand_calls = 0
    for (i = 1; i <= n; i++) {
        k = ks[i]; split(k, a, SUBSEP)
        printf "%-10s  %-9s  %5d  %8d  %8d  %8.4f  %8.1f\n", \
            a[1], a[2], calls[k], tin[k], tout[k], usd[k], sec[k]
        grand_calls += calls[k]; grand_in += tin[k]; grand_out += tout[k]
        grand_usd += usd[k]; grand_sec += sec[k]
    }
    if (n > 0)
        printf "%-10s  %-9s  %5d  %8d  %8d  %8.4f  %8.1f\n", \
            "TOTAL", "-", grand_calls, grand_in, grand_out, grand_usd, grand_sec
}
