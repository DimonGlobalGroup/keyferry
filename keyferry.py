#!/usr/bin/env python3
"""KeyFerry — config-key parity gate for dotenv-style files.

Audits KEY=value files for structural problems and checks them
against a template for key parity: missing keys, extra keys,
duplicate keys, malformed lines, empty values. Values are never
printed in any mode — only key names, line numbers, and counts —
so a report is safe to paste into a ticket or a log.

Read-only, Python standard library only, no network access.
Exit codes: 0 = no error findings, 1 = error findings,
2 = usage or I/O error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys

__version__ = "1.0.0"

_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_UPPER_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")

ERROR_CODES = {
    "malformed-line",
    "duplicate-key",
    "missing-key",
}


class UsageError(Exception):
    """I/O or usage problem -> exit 2."""


def parse_file(path):
    """Parse one dotenv-style file.

    Returns (entries, findings) where entries is a list of
    (key, lineno, has_value) in file order and findings is a list of
    dicts. Values are read only to test emptiness and are never
    stored or returned.
    """
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            lines = fh.read().splitlines()
    except OSError as exc:
        raise UsageError(f"cannot read {path}: {exc.strerror or exc}")
    entries = []
    findings = []
    seen = {}
    for lineno, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        if "=" not in line:
            findings.append({"code": "malformed-line", "line": lineno})
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not _KEY_RE.match(key):
            findings.append({"code": "malformed-line", "line": lineno})
            continue
        has_value = value.strip() != ""
        if key in seen:
            findings.append({
                "code": "duplicate-key", "key": key,
                "line": lineno, "first_line": seen[key],
            })
        else:
            seen[key] = lineno
        if not has_value:
            findings.append({"code": "empty-value", "key": key, "line": lineno})
        if not _UPPER_RE.match(key):
            findings.append({"code": "nonstandard-key", "key": key, "line": lineno})
        entries.append((key, lineno, has_value))
    keys = [k for k, _, _ in entries]
    for i in range(1, len(keys)):
        if keys[i] < keys[i - 1]:
            findings.append({
                "code": "unsorted-keys", "key": keys[i],
                "line": entries[i][1], "after": keys[i - 1],
            })
            break
    return entries, findings


def audit_file(path):
    entries, findings = parse_file(path)
    return {"path": path, "keys": len({k for k, _, _ in entries}),
            "entries": entries, "findings": findings}


def check_file(template, target):
    """Audit target and compare its key set against the template's."""
    result = audit_file(target)
    t_keys = {k for k, _, _ in template["entries"]}
    have = {}
    for key, lineno, has_value in result["entries"]:
        have.setdefault(key, (lineno, has_value))
    findings = list(result["findings"])
    # In check mode an empty value for a template key is an error.
    findings = [
        {**f, "severity": "error"} if f["code"] == "empty-value"
        and f.get("key") in t_keys else f
        for f in findings
    ]
    for key in sorted(t_keys - set(have)):
        findings.append({"code": "missing-key", "key": key})
    for key in sorted(set(have) - t_keys):
        findings.append({"code": "extra-key", "key": key,
                         "line": have[key][0]})
    result["findings"] = findings
    return result


def severity(finding):
    if "severity" in finding:
        return finding["severity"]
    return "error" if finding["code"] in ERROR_CODES else "warning"


def render(results, as_json, max_examples):
    errors = warnings = total_keys = 0
    out = []
    payload = []
    for r in results:
        counts = {}
        for f in r["findings"]:
            counts[f["code"]] = counts.get(f["code"], 0) + 1
            if severity(f) == "error":
                errors += 1
            else:
                warnings += 1
        total_keys += r["keys"]
        shown = {}
        suppressed = {}
        for f in sorted(r["findings"],
                        key=lambda f: (f["code"], f.get("line", 0))):
            bucket = shown.setdefault(f["code"], [])
            if len(bucket) < max_examples:
                bucket.append(f)
            else:
                suppressed[f["code"]] = suppressed.get(f["code"], 0) + 1
        payload.append({"path": r["path"], "keys": r["keys"],
                        "counts": counts, "findings": shown,
                        "suppressed": suppressed})
        if not as_json:
            out.append(f"== {r['path']} ({r['keys']} keys)")
            for code in sorted(shown):
                for f in shown[code]:
                    bits = [code]
                    if "key" in f:
                        bits.append(f["key"])
                    if "line" in f:
                        bits.append(f"line {f['line']}")
                    if "first_line" in f:
                        bits.append(f"first line {f['first_line']}")
                    if "after" in f:
                        bits.append(f"after {f['after']}")
                    out.append("  " + " ".join(bits))
                if code in suppressed:
                    out.append(f"  {code} ... and {suppressed[code]} more")
            if not counts:
                out.append("  ok")
    summary = (f"keyferry: {len(results)} files, {total_keys} keys, "
               f"{errors} errors, {warnings} warnings")
    if as_json:
        return json.dumps({"files": payload, "summary": summary},
                          indent=2, sort_keys=True) + "\n", errors
    out.append(summary)
    return "\n".join(out) + "\n", errors


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="keyferry",
        description="Config-key parity gate: audit dotenv-style files "
                    "and check them against a template. Values are "
                    "never printed.")
    ap.add_argument("--version", action="version",
                    version=f"keyferry {__version__}")
    sub = ap.add_subparsers(dest="command")
    for name in ("audit", "check"):
        p = sub.add_parser(name)
        p.add_argument("files", nargs="+")
        p.add_argument("--json", action="store_true")
        p.add_argument("--max-examples", type=int, default=10)
        if name == "check":
            p.add_argument("--template", required=True)
    args = ap.parse_args(argv)
    if not args.command:
        ap.print_usage(sys.stderr)
        return 2
    if args.max_examples < 0:
        print("keyferry: --max-examples must be >= 0", file=sys.stderr)
        return 2
    try:
        if args.command == "audit":
            results = [audit_file(p) for p in args.files]
        else:
            template = audit_file(args.template)
            t_errors = sum(1 for f in template["findings"]
                           if severity(f) == "error")
            if template["findings"]:
                text, _ = render([template], args.json, args.max_examples)
                sys.stdout.write(text)
                if t_errors:
                    return 1
            results = [check_file(template, p) for p in args.files]
    except UsageError as exc:
        print(f"keyferry: {exc}", file=sys.stderr)
        return 2
    text, errors = render(results, args.json, args.max_examples)
    sys.stdout.write(text)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
