# KeyFerry

**Does this machine's config file carry exactly the keys the template
promises — no more, no fewer, no duplicates, nothing malformed?**

KeyFerry is a single-file, stdlib-only Python gate for dotenv-style
`KEY=value` files. It audits config files for structural problems and
checks them against a template (your `.env.example`) for key parity:
missing keys, extra keys, duplicates, malformed lines, empty values.

**Values are never printed — in any mode.** No code path emits a
value: not in text output, not in JSON, not in an error message.
Reports carry key names, line numbers, and counts only, so a parity
report is safe to paste into a ticket, a log, or a chat.

## Why

Secret scanners answer "did a value leak?" Loaders answer "what is
my app's config?" Neither answers the drift question that breaks
deploys at 2 a.m.: *this machine is missing a key the template
promises* — or carries a duplicate that one loader resolves one way
and another loader resolves the other way. KeyFerry is that check,
in the shape of a gate: exit 0, 1, or 2, deterministic output, no
network, no writes.

## Install

Copy `keyferry.py` anywhere. Python 3.10+, standard library only.

## Usage

Audit one or more files:

```console
$ cat app.env
ALPHA=one
BETA=
BETA=two
lower_case=1

$ python3 keyferry.py audit app.env
== app.env (3 keys)
  duplicate-key BETA line 3 first line 2
  empty-value BETA line 2
  nonstandard-key lower_case line 4
keyferry: 1 files, 3 keys, 1 errors, 2 warnings
$ echo $?
1
```

Check files against a template:

```console
$ python3 keyferry.py check --template .env.example prod.env staging.env
```

In `check` mode, a template key missing from a target is an error,
a target key absent from the template is a warning, and an empty
value for a template key is an error (in plain `audit` it is a
warning — an empty value may be intentional outside a template
contract).

Options: `--json` for machine-readable output, `--max-examples N`
(cap findings shown per code per file, default 10; suppressed
findings are counted, never hidden).

## Findings

| Code | Severity | Meaning |
|---|---|---|
| `malformed-line` | error | not a valid `KEY=value` assignment |
| `duplicate-key` | error | key assigned more than once (both lines shown) |
| `missing-key` | error (`check`) | template key absent from the target |
| `empty-value` | warning / error in `check` for template keys | key assigned no value |
| `extra-key` | warning (`check`) | target key absent from the template |
| `nonstandard-key` | warning | key is not UPPER_SNAKE_CASE |
| `unsorted-keys` | warning | keys are not in ascending order (first break shown) |

Exit codes: `0` no error findings · `1` error findings ·
`2` usage or I/O error (a missing or unreadable file is exit 2,
never a traceback).

## Honest limits

- KeyFerry audits key *structure*, not value semantics: quoting,
  interpolation, and multiline values are not interpreted; the
  value is everything after the first `=`.
- "Values are never printed" covers this tool's output. It does
  not scrub your shell history, your editor, or the file itself.
- Parity is about key names. Two files can pass parity and still
  hold different values — that difference is yours to manage, and
  KeyFerry deliberately never looks at it beyond empty/not-empty.

## License

MIT — see `LICENSE`. Copyright (c) 2026 Dimon Global Group.
