# Contributing

The Wagering Policy Data Center is a reference. Its value is that every number
can be traced to a primary source and that a second person has checked it.
This document explains how to add or correct data and how review works.

## Ground rules

1. **Primary sources only.** A figure is cited to the body that produced it:
   a regulator's report, a court's opinion, a legislature's journal, a paper's
   PDF. Trade press and trackers may be used to find a document, never as the
   cited source. The validator rejects tertiary sources.
2. **Separate the three markets.** Regulated sportsbooks, prediction markets
   (CFTC-designated event contract exchanges) and offshore or sweepstakes
   products are never combined. Every market-related record carries a
   `market_segment`.
3. **Describe, do not advocate.** Copy says what a statute does, what a court
   held, what a paper found and what its limitations are. It does not say
   whether any of that is good.
4. **No em dashes or en dashes** anywhere. The build fails on them.
5. **Nothing derived is stored.** Per capita figures, rates and grades are
   computed at build time.

## Setup

```
npm install
python3 -m venv .venv && . .venv/bin/activate
pip install -e ingest[dev]
npm run build          # runs validate, dash lint, then builds the site
```

`python3 scripts/validate.py` alone checks the data without building.

## Record status and review

Every record has a provenance block with a `status`:

| status | meaning |
| --- | --- |
| `pending_review` | Entered with a citation; awaiting a second person. Renders with a badge. Excluded from grades and headline figures. |
| `verified` | A reviewer checked the value against the source. `reviewed_by` is set. |
| `unverified` | Placeholder; value not read from the source. Renders as "not entered". |
| `disputed` | A public issue challenges the value. Stays visible with a badge and link. |
| `superseded` | Replaced by a later record. Kept for history. |

**Two-person rule.** You enter a record as `pending_review`. A different
contributor with the data-reviewer role opens your pull request, follows each
source link, confirms each value, and approves. On merge the status flips to
`verified` and the approver's handle is recorded in `reviewed_by`. You cannot
verify your own entry.

**Disputes.** Open an issue with the `data-dispute` label naming the file,
the record and the primary source that contradicts it. A maintainer sets the
record to `disputed` until resolved by a pull request.

**Publisher restatements.** When a regulator restates a month or a paper
posts a new draft, add a new record and set the old one to `superseded`. Do
not edit the old value in place.

## How to add a state (or complete a status-only profile)

1. Open `data/states/<abbr>/profile.yaml`. Every state already has one with
   `legal_status` and `regulators`.
2. Fill the sections in this order, each with its own provenance block:
   `legal_age`, `tax`, `consumer_protections` (self-exclusion, deposit
   limits, advertising, credit card deposits, helpline message),
   `limitations`.
3. Cite the statute or regulation section for each item, not the regulator's
   summary page, unless the regulator's page is the only published source.
4. Create `pg_funding.yaml` from the appropriations act or the fund report.
   If you know the mechanism but not the amount, enter the mechanism and
   leave `amount_usd: null` with a note saying where the amount will come
   from.
5. Create `prediction_markets.yaml`. If you find no state action, say in
   `review_note` what you searched.
6. Set `profile_completeness: full` only when every section is entered.
7. If you cite a new publisher, add it to `data/sources/sources.yaml` first.
8. Run `python3 scripts/validate.py`, open a pull request, and fill in the
   data review section of the template.

Field definitions and allowed values are in `schemas/state_profile.schema.json`
and `docs/design/01-data-model.md`.

## How to add a bill

1. Create `data/legislation/bills/<st>-<year>-<billnumber>.yaml`, for
   example `ok-2026-hb1047.yaml`. Copy the existing file as a template.
2. `summary` and `would` describe the bill's provisions neutrally.
3. Votes cite the chamber journal or the official roll call page. A vote
   count from press is `pending_review` with a note until the journal is
   checked.
4. Link `text_url` to the legislature's own bill page.
5. Fiscal estimates come from the fiscal note. Do not enter revenue
   estimates from press; they vary widely and are not data.

## How to add a paper

1. Create `data/research/papers/<firstauthor-...-year>.yaml`.
2. Record every version you can find under `versions`, with the date (and
   `date_precision` if only the month or year is known) and URL. Once the
   PDF is archived, add its `sha256`.
3. Each `key_figures` entry names the version it comes from, the
   specification (table, estimator, horizon) and the value as the paper
   states it. If a later draft changes a figure, add a new figure entry and
   mark the old one `superseded` with `superseded_by`. If one draft reports
   two figures under different specifications, enter both.
4. `unit_of_effect` is required. Population averages, household-level and
   bettor-level effects are different claims.
5. The plain-language summary describes what was studied, what was found,
   and the main caveats. No recommendations.

## How to run an ingestion module

```
wpdc list
wpdc ingest uscourts-bankruptcy-f2 --period 2026-Q2            # fetch, archive, parse, write, print review checklist
wpdc ingest nj-dge-sports-wagering-monthly --period 2026-09
wpdc ingest nj-dge-sports-wagering-monthly --period 2026-09 --local ~/Downloads/September2026.pdf   # manual drop
```

If your machine cannot reach the publisher (some development containers
cannot), commit a request file instead and let GitHub Actions do the fetch:

```
cat > ingest/requests/nj-dge-2026-09.yaml <<'EOF2'
kind: ingest
source_id: nj-dge-sports-wagering-monthly
period: 2026-09
EOF2
git add ingest/requests && git commit -m "ingest request: NJ DGE September 2026" && git push
```

The `Ingest requests` workflow runs every file in that directory, prints
the review checklist and a summary of what it fetched into the job log,
uploads the data and the raw archive as artifacts, and pushes a copy to an
`ingest-results/run-N` branch when the repository allows it. A maintainer
inspects the checklist, commits the rows, and deletes the request file.
See `ingest/requests/README.md`.

The module archives the document under `archive/raw/<source_id>/<sha256>`,
requests a Wayback capture, parses against a known layout, and writes rows
with `status: pending_review`. If the document's layout has changed, the
module stops with a `LayoutChanged` error describing what it saw. Do not
work around it: add a fixture under `ingest/tests/fixtures`, add a parser
branch, add a test, and open a pull request.

## Adding a source module

Implement the protocol in `ingest/wpdc_ingest/core/source.py`
(`discover`, `parse`, `normalize`), register it in
`ingest/wpdc_ingest/sources/__init__.py`, add the publisher to
`data/sources/sources.yaml`, and add a fixture-based test. `parse` must be a
pure function of the document.

## Style

- Dates ISO 8601 in data, written out in copy.
- Money as integer dollars in data.
- Rates as decimals in data (0.13), percentages in copy.
- State the procedural posture of any court ruling (preliminary relief or
  final judgment).
