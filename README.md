# Wagering Policy Data Center

An open, nonpartisan public data portal tracking the state-by-state status and
consequences of legalized sports betting and prediction markets in the United
States. Modeled on the CDC STATE System and state report card projects. The
audience is state legislators and staff, journalists and researchers.

Draft site: https://jst-jdennis.github.io/sportsbettingstats/

## Principles

- Every number links to its primary source and shows the date retrieved. The
  page templates cannot render a figure without a provenance record.
- Regulated sportsbooks, prediction markets and offshore or sweepstakes
  products are never conflated.
- Evidence is presented with its limitations on the same page. Copy
  describes; it does not advocate.
- All data is version-controlled, schema-validated on every build, and
  licensed CC BY 4.0. Code is AGPL-3.0.

## Status

Draft. All 50 states and DC have a legal status entry, marked pending
review until a second contributor checks it. Oklahoma, New Jersey and Kansas
have complete profiles. The outcome time series (New Jersey monthly revenue,
nonbusiness bankruptcy filings for every state since 2018, helpline contacts,
prevalence studies), the research library, the legislation tracker and the
report cards are built and populated from primary documents. Every table and
chart has a CSV sibling with the same columns plus per-row provenance, every
page has a `data.csv` in long format and a citation widget, and every state
has a fact sheet PDF with every figure footnoted to its source. Every page
carries a build-time SVG chart (no client JavaScript) with its data table. See
`docs/design/` for the data model, source inventory and ingestion design.

## Layout

```
data/        version-controlled data files (YAML entities, CSV time series)
schemas/     JSON Schema and Frictionless Table Schema for every dataset
scripts/     validate.py and lint_dashes.py, run on every build
src/         Astro site (static output, no client JavaScript required)
ingest/      Python ingestion layer, one module per source, fixture-tested
docs/design/ design documents
```

## Build

```
npm install
python3 -m venv .venv && . .venv/bin/activate && pip install -e ingest[dev]
npm run build        # validate + lint + astro build -> dist/
```

See `CONTRIBUTING.md` for how to add a state, a bill or a paper and how
review works.
