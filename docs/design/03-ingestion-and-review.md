# Ingestion layer and review workflow

Status: draft for review. Date: 2026-10-16.

The brief identifies this as where the real value is: 39 regulators, 39
formats, and a contributor base that will mostly be doing careful manual
entry from PDFs. The design optimizes for three things, in order:
correctness of each number, auditability of how it got there, and low
friction for a careful contributor who is not a programmer.

## 1. Layout

```
ingest/
  pyproject.toml
  wpdc_ingest/
    core/
      source.py        Source base class and registry loader
      provenance.py    Provenance block construction, Wayback archiving
      archive.py       Local raw-document store, content hashing
      writers.py       CSV and YAML writers that preserve ordering and diffs
      validate.py      Calls the same schema validators the site build uses
      review.py        Generates the review checklist for a pull request
    sources/
      uscourts_bankruptcy.py
      census_population.py
      nj_dge_sports_wagering.py
      ks_lottery_sports_wagering.py
      legiscan_bills.py
      ...
    cli.py             `wpdc ingest <source> [--period ...]`, `wpdc review`, `wpdc validate`
  tests/
    fixtures/          Captured raw documents, one per source and layout version
archive/
  raw/<source_id>/<sha256>.<ext>   Every retrieved document, immutable
  raw/<source_id>/index.jsonl      Hash, URL, retrieved_at, Wayback URL
```

## 2. Source module contract

Every module implements one class:

```python
class Source(Protocol):
    source_id: str                      # must exist in data/sources/sources.yaml
    access_method: AccessMethod
    def discover(self, period: Period | None) -> list[Document]
        # Find the documents for a period: URLs, or paths for manual drops.
    def fetch(self, doc: Document) -> RawDocument
        # Download, hash, store under archive/raw, submit to Wayback.
    def parse(self, raw: RawDocument) -> list[Record]
        # Pure function. Raises LayoutChanged on fingerprint mismatch.
    def normalize(self, records: list[Record]) -> list[Row]
        # Map to the dataset schema. Attach provenance. Document transform.
```

Rules:

- `parse` is pure and tested against fixtures. When a regulator changes a
  PDF layout, the module raises `LayoutChanged` with the fingerprint diff,
  and the contributor adds a new fixture and parser branch. No silent
  best-effort parsing.
- `normalize` writes `transform` text into provenance automatically from
  the operations applied (for example "summed 4 retail licensee rows;
  promo deductions column mapped to promo_deductions_usd").
- Every fetched document is archived locally and to the Wayback Machine
  before parsing. The archive URL goes into provenance. If Wayback fails,
  the local hash is recorded and a retry is queued; the record is allowed
  through with `archive_url` null and a warning.
- Modules never write directly to `main`. The CLI writes files to the
  working tree and the contributor or the scheduled action opens a pull
  request.

## 3. Access patterns, by difficulty

### 3.1 Structured (API or bulk download)

US Courts tables, Census, LegiScan, Open States, CourtListener. Fully
automated. Scheduled GitHub Action runs on the source cadence, opens a
pull request titled `data(<source_id>): <period>` with the review
checklist in the body, and assigns the data reviewers team.

### 3.2 Semi-structured (xlsx or consistent HTML tables)

New York, Pennsylvania and several others. Automated with a layout
fingerprint (sheet names, header row text, column count). Fingerprint
mismatch fails the run and opens an issue instead of a pull request.

### 3.3 PDF with stable layout

Many regulators. Parsed with `pdfplumber` table extraction against a
per-layout template that names the expected row labels. Each value is
cross-checked against any totals row in the same document; a mismatch
beyond rounding fails the run. Extracted values are written with
`status: pending_review` and the review checklist includes the page image
with the extracted cells highlighted, so the reviewer compares the number
to the PDF, not to the parser's opinion of the PDF.

### 3.4 Manual entry

For irregular PDFs, press releases with embedded numbers, statute reading,
enforcement letters, prevalence studies and papers. The workflow is a
form, not a text editor:

1. Contributor runs `wpdc entry new <dataset>` (or uses the web form, see
   section 5) which asks for each field in order, with the schema's
   descriptions and allowed values shown inline, and requires a source URL
   and the page or table reference for every numeric field.
2. The tool fetches and archives the source document, records
   `retrieved_at`, and writes the YAML or CSV row with
   `status: pending_review` and `entered_by`.
3. The tool runs validation and opens a pull request from a branch.

No contributor edits a CSV by hand in a spreadsheet application. Excel
silently reformats dates and strips leading zeros from FIPS codes.

## 4. Review workflow

Two-person rule for anything that renders as a figure.

1. **Entry.** Record enters with `status: pending_review`. It renders on
   preview builds with a badge and does not render on production.
2. **Review.** A second contributor with the `data-reviewer` role opens the
   pull request. The automated review checklist in the pull request body
   contains, for each changed record: the value, the source link, the
   archive link, the page reference, and (for parsed PDFs) the cropped
   page image. The reviewer confirms each by checking the box. The
   `reviewed_by` field is set by the merge bot from the approving
   reviewer's handle; it cannot be set by the author.
3. **Status flip.** On approval, the bot sets `status: verified` and merges.
   Production rebuilds.
4. **Disputes.** Anyone can open an issue with the `data-dispute` label
   citing a record. The record is set to `disputed` (still renders, with a
   visible flag and a link to the issue) until resolved. Resolution is a
   pull request that either corrects the record (old row becomes
   `superseded`, new row `verified`) or closes the dispute with a written
   reason recorded in `notes`.
5. **Revisions from the publisher.** When a regulator restates a month,
   the ingestion run produces a new row with `is_revised: true`, marks the
   old row `superseded`, and the review checklist shows both values. The
   site's revision log for that series lists every superseded row.

CODEOWNERS routes files by directory so that, for example, research
library changes require a reviewer from the research group and
legislation changes require one from the legislation group.

## 5. Contributor surfaces

Three, in order of expected volume:

1. **GitHub pull requests** created by the CLI or the scheduled action.
   This is the system of record.
2. **A web entry form** (static page with a small amount of JavaScript)
   that produces a pre-filled GitHub issue or pull request via the GitHub
   web flow, for contributors who will not install Python. The form
   validates against the same JSON Schema in the browser. Phase 2.
3. **An issue template** for "report a number" with required fields for
   source URL, page, value and date. Lowest friction, highest review load.

`CONTRIBUTING.md` documents all three with worked examples for the three
tasks the brief names: adding a state, adding a bill, adding a paper.

## 6. Staleness and coverage reporting

The build generates a coverage page: for each dataset and state, the
latest period held, the expected cadence, and a staleness flag. The same
page lists states with no data and the reason (`no_legal_market`,
`regulator_does_not_publish`, `not_yet_ingested`, `publishes_but_paywalled`).
A hostile reader should be able to see exactly what the site does not
know. This page is also the maintainers' work queue.

## 7. Phase 1 working sources

Two automated modules will be fully working in Phase 1:

1. `uscourts_bankruptcy`: downloads F-2 (district) quarterly tables from
   2007 onward, maps districts to states, writes `outcomes/bankruptcy.csv`.
   Chosen because it is structured, national, and exercises the
   derived-rate and annotation machinery end to end.
2. `nj_dge_sports_wagering`: parses the New Jersey monthly sports wagering
   reports from June 2018 onward into `outcomes/handle_revenue.csv`. Chosen
   because it is the longest series and a PDF, which exercises the layout
   fingerprint, archive and page-image review path.

`census_population` is also required (per capita denominators) and is
trivial, so it ships in Phase 1 as well but is not counted as one of the
two.
