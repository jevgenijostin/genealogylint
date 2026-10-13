# GenealogyLint

An offline GEDCOM family-tree validator and relationship calculator. Python
3.10+; no UI, telemetry, services, or runtime dependencies outside the standard
library. Your tree stays on your machine. This is a deliberately small MVP,
not a complete GEDCOM implementation or a genealogy editor.

## Install and run

```sh
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e .
genealogylint validate tests/fixtures/relationships.ged
genealogylint validate family.ged --json
genealogylint relate tests/fixtures/relationships.ged A C
# first cousin
genealogylint relate tests/fixtures/relationships.ged D F
# second cousin once removed
```

`python -m genealogylint` is equivalent to the installed command. `relate`
describes **the first person's relationship to the second**. IDs can be `I1`
or quoted `"@I1@"`; IDs are case sensitive. Missing IDs produce an input error.

Validation prints a severity-ranked table. JSON is an object with `file`,
`individual_count`, and `findings`; each finding has `severity`, `code`, `ids`,
and `message`. Findings sort by severity, code, then IDs. Exit codes:

* **0:** valid execution with no ERROR findings (warnings/info are allowed).
* **1:** validation completed with ERROR findings.
* **2:** invalid input, invalid options, unreadable file, or license restriction.

Errors go to stderr. JSON stdout stays empty on input errors, including a failed
file in a batch. Files are read only; nothing is repaired automatically.

## Supported GEDCOM subset

* UTF-8 (optional BOM), LF or CRLF; blank lines accepted.
* Level-numbered lines and unique `@...@` cross-reference IDs.
* `INDI`: one `NAME`, `SEX`, one `BIRT/DATE` and one `DEAT/DATE`.
  Name slashes are removed and whitespace normalized. SEX is retained; output
  uses gender-neutral labels.
* `FAM`: `HUSB`, `WIFE`, repeated `CHIL`, and one `MARR/DATE`.
  Multiple family records per person are supported. At most two distinct
  spouses per family. Repeated identical member references are deduplicated.
* Optional `FAMC`/`FAMS` pointers are checked for existing, reciprocal family
  membership. The FAM records define the parent/spouse graph; individual-side
  pointers are not required. Missing or inconsistent pointers fail parsing.
* Dates: `YYYY`, `MON YYYY`, `D MON YYYY`, and `ABT`, `BEF`, `AFT`,
  `BET ... AND ...` with English GEDCOM month abbreviations. Gregorian years
  0001–9999 only. Invalid or unsupported dates in supported events fail parsing.
* Unknown tags/records (including header metadata) are ignored after structural
  checking. A HEAD/TRLR envelope is optional. Empty files are empty trees.
  Skipped levels, malformed lines, duplicate IDs, missing referenced individuals,
  and repeated supported scalar fields produce input errors with context.

Dates are inclusive intervals: a year spans the year; a month spans the month.
BEF ends the day before the earliest possible date; AFT starts the day after
the latest possible date. BET includes both endpoints. ABT is an explicit MVP
heuristic: the entire preceding year through the entire following year, even
when a day is supplied. Unrepresentable strict boundaries fail parsing.

## Validation rules

| Severity | Check | Default semantics |
| --- | --- | --- |
| ERROR | Circular ancestry | Iterative DFS over parent edges; reports back-edge cycle witnesses, including self-parenting |
| ERROR | Death before birth | Latest possible death precedes earliest possible birth |
| ERROR | Marriage before birth | Latest possible marriage precedes either spouse's earliest birth |
| ERROR | Marriage after death | Earliest possible marriage follows either spouse's latest death |
| WARNING | Implausible parent age | Definitely younger than 12 or older than 75 completed years at child's birth |
| WARNING | Implausible death age | Definitely older than 120 completed years |
| WARNING | Possible duplicates | Same normalized, case-insensitive full name and identical normalized birth-date expression, or both birth dates absent |
| INFO | Orphan | Individual is not a member of any FAM record |

Date comparisons and age checks report only provable violations across the
entire interval. Missing/unbounded endpoints can prevent a check; silence is
not proof that a chronology is correct. Ages use calendar birthdays, not
365-day approximations; leap-day birthdays advance on March 1 in non-leap years.
Thresholds are inclusive, so exactly 12, 75, and 120 do not trigger warnings.

```sh
genealogylint validate family.ged --min-parent-age 14 --max-parent-age 80 --max-death-age 115
```

Duplicate groups generate one finding per group; blank names are excluded.
No fuzzy spelling, phonetic, or overlapping-date duplicate matching is attempted.
Membership in even a one-person FAM counts as a link for the orphan rule.

## Relationships and simplifications

Breadth-first traversal computes shortest generation distances to each ancestor
(including the person). Among common ancestors, choose the smallest maximum
distance, then smallest total distance, then lexical ID. This produces one
deterministic closest common-ancestor relationship; it does not enumerate all
relationships in a pedigree with multiple ancestry paths.

Supported labels include self, spouse, parent/child, grandparent/grandchild,
arbitrary great- prefixes, sibling, half-sibling, aunt/uncle, niece/nephew,
Nth cousins and removals, and no known relationship. A half-sibling label
requires exactly one shared parent plus a different known parent on each side.
With incomplete parentage the label is sibling; half-cousins and half-aunts
are not distinguished. Cousin degree is `min(distance1, distance2) - 1`;
removal is the absolute distance difference.

Spouse takes precedence, followed by blood relationships, then simple in-laws.
In-laws traverse exactly one spouse edge to a parent, child, or sibling and
return parent-in-law, child-in-law, or sibling-in-law. Multiple possible
in-laws resolve by sorted spouse ID. Two spouse edges, step-relatives, and
more distant affinal relationships are not calculated. A tree containing any
ancestry cycle is rejected by `relate`; use `validate` first to locate it.

## Free tier and demo PRO license

The CLI is fully functional for **up to 100 individuals per tree**. Larger trees
and batch validation require a local checksum key. This follows ScamSniff's
demo-license pattern: eight uppercase alphanumeric payload characters and a
four-digit rolling checksum. It is intentionally forgeable, not authentication,
DRM, or a payment integration. The Python library itself is not license-gated.

Generate a demo key locally:

```sh
python -c "from genealogylint.license import create_demo_key; print(create_demo_key())"
genealogylint validate large.ged --license-key GL-PRO-DEMO2026-XXXX
genealogylint validate one.ged two.ged --batch --json --license-key GL-PRO-DEMO2026-XXXX
```

Replace the placeholder with the printed key. Alternatively set the environment
variable `GENEALOGYLINT_LICENSE`; `--license-key` overrides it on either command.
Batch mode requires PRO even for small files and returns a JSON array in input
file order. Without `--batch`, validate accepts exactly one file. Relationships
operate on one file at a time.

Real Gumroad/LemonSqueezy payments, signed licenses, issuance and revocation are
follow-up work, **not built into this MVP**. There is no online activation.

## Honest limitations / TODO

* Not a full GEDCOM 5.5.1 conformance checker; GEDCOM 7 is not supported.
* ANSEL/UTF-16, non-Gregorian calendars, BCE/dual dates, CAL/EST/FROM/TO,
  free-text date phrases, and date interpretation are unsupported.
* Adoption, foster/step parentage, PEDI and adoption-specific tags are ignored;
  all FAM spouse-to-child edges are treated alike. Do not use this to infer
  biological parentage when the export includes adoption metadata.
* Multiple marriages across distinct FAM records work, but divorce, annulment,
  remarriage chronology, repeated MARR events in one family, current-vs-former
  spouse status, and multiple simultaneous relationships are not modeled.
  All recorded spouse pairs remain spouse/in-law links regardless of date.
* Alternate names, sources, citations, notes, media, places, custom extensions,
  CONT/CONC continuation semantics, and events beyond the supported ones are
  ignored. Repeated NAME/date fields are rejected instead of selecting one.
* No fuzzy duplicates, gender-based assumptions, file rewriting, merging, UI,
  or automatic fixes. No relationship confidence score or path explanation.
* Files and reports are held in memory. Traversals are iterative, but this is
  not a streaming tool or a benchmarked million-person genealogy engine.
* Unknown tags do not produce warnings. Inspect these limitations before
  interpreting a clean report as complete coverage of an export.

## Tests and offline audit

```sh
python -m unittest discover -s tests -v
```

The stdlib unittest suite uses small handcrafted GEDCOM fixtures for every rule
and relationship-degree cases, plus malformed input, dates, CLI/JSON, licensing,
deep ancestry, and pedigree collapse. CI installs the package and runs the suite
on Ubuntu and Windows with Python 3.10, 3.12, and 3.14.

Runtime dependencies: **none**. Application source can be inspected with:

```sh
rg -n -i 'https?://|\b(fetch|XMLHttpRequest|requests|urllib|httpx|aiohttp|socket|http|ftplib|smtplib|webbrowser)\b' src
```

Expected: no matches (rg exit 1). Installation/build tools and GitHub Actions
may access package registries/GitHub; the installed application does not make
network calls. MIT licensed.
