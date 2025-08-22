#!/usr/bin/env python3
import sys, json, argparse

def decode_line(s: str):
    """
    Try to interpret s as:
      1) A JSON array already (list)
      2) A JSON string that itself contains a JSON array (double-encoded)
      3) A quoted CSV-style string with doubled quotes -> unescape and parse
    Returns a Python list (possibly empty). Raises ValueError if not parseable.
    """
    s = s.strip()
    if not s:
        return []

    # Try direct JSON parse first
    try:
        v = json.loads(s)
        if isinstance(v, list):
            return v
        # If it parsed into a string, maybe it's a double-encoded JSON array
        if isinstance(v, str):
            v2 = json.loads(v)
            if isinstance(v2, list):
                return v2
    except Exception:
        pass

    # Try CSV-style: remove surrounding quotes and undouble quotes
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        inner = s[1:-1].replace('""', '"')
        try:
            v3 = json.loads(inner)
            if isinstance(v3, list):
                return v3
        except Exception:
            pass

    raise ValueError("Could not parse input line as a JSON array (single or double-encoded).")

def to_md_links(arr):
    """
    From a list of dicts, build ["[label](url)", ...]
    Only include items that have both 'label' and 'url' (case-sensitive).
    """
    out = []
    for item in arr:
        if isinstance(item, dict):
            label = item.get("label")
            url = item.get("url")
            if isinstance(label, str) and isinstance(url, str):
                out.append(f"[{label}]({url})")
    return out

def process_stream(fin, fout, strict=False):
    """
    Read lines from fin, write converted JSON arrays to fout.
    If strict=True, any line that fails to parse aborts with an error.
    If strict=False, lines that fail to parse produce [].
    """
    for ln, raw in enumerate(fin, start=1):
        raw = raw.rstrip("\n")
        if not raw.strip():
            fout.write("[]\n")
            continue
        try:
            arr = decode_line(raw)
            md = to_md_links(arr)
            fout.write(json.dumps(md, ensure_ascii=False) + "\n")
        except Exception as e:
            if strict:
                print(f"Error on line {ln}: {e}", file=sys.stderr)
                sys.exit(1)
            else:
                # Graceful fallback
                fout.write("[]\n")

def main():
    ap = argparse.ArgumentParser(description="Convert arrays of objects with label/url into arrays of Markdown links.")
    ap.add_argument("-i", "--input", help="Input file (default: stdin)")
    ap.add_argument("-o", "--output", help="Output file (default: stdout)")
    ap.add_argument("--strict", action="store_true", help="Fail on the first unparseable line.")
    args = ap.parse_args()

    fin = open(args.input, "r", encoding="utf-8") if args.input else sys.stdin
    fout = open(args.output, "w", encoding="utf-8") if args.output else sys.stdout
    try:
        process_stream(fin, fout, strict=args.strict)
    finally:
        if fin is not sys.stdin:
            fin.close()
        if fout is not sys.stdout:
            fout.close()

if __name__ == "__main__":
    main()

