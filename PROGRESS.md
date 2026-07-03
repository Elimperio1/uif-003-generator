# Build Progress

> 2026-07-02 — FORMAT.md rewritten from the UIF eDecs handoff spec:
> `uuuuuuuu.nnn` naming, fields 8220/8290, status codes 01–19,
> non-contribution reason codes 1–6, validation rules A–D. Handoff
> conflicts with the analysed sample file in five places — see
> "Discrepancies vs. sample file" in FORMAT.md; resolve during Step 3.

## Step 1 — Scaffold
Status: **smoke-tested, merged to `main` (2026-07-03)**
Branch: `step-1-scaffold`
Scope:
- Project skeleton, requirements, .gitignore
- Streamlit entry point with shared-password auth gate
- Two file-upload widgets and intro instructions
- Stub modules for parsing / matching / generation / validation
- 003 format specification (FORMAT.md)
- README with local-dev and deploy instructions

## Step 2 — Parsers + matcher (planned)
- Implement parse_ytd, parse_employees, match.join
- Keep zero-contribution employees in the join (Rule D)
- Anonymised test fixtures in samples/

## Step 3 — Generator + validator (planned)
- Implement generate_003.build with byte-exact output (rules A/B/C)
- Implement validate.validate for soft errors (identity, Rule D, caps)
- Diff test against samples/expected .003 file — resolve the five
  handoff-vs-sample discrepancies listed in FORMAT.md

## Step 4 — UI wiring (planned)
- Month range picker + sequential batch number input (`.nnn`)
- Soft error display
- Single-file or zip download
- Pull company info from CSV headers (or prompt once)
