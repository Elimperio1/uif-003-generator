# Build Progress

## Step 1 — Scaffold
Status: **awaiting smoke test**
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
- Anonymised test fixtures in samples/

## Step 3 — Generator + validator (planned)
- Implement generate_003.build with byte-exact output
- Implement validate.validate for soft errors
- Diff test against samples/expected.003

## Step 4 — UI wiring (planned)
- Month range picker
- Soft error display
- Single-file or zip download
- Pull company info from CSV headers (or prompt once)
