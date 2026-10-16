# Ingestion requests

Commit a YAML file here to have GitHub Actions (which has internet access,
unlike some development containers) fetch, archive and parse documents.
The workflow `.github/workflows/ingest.yml` runs on any push that changes a
file in this directory and uploads the results as workflow artifacts:

- `data-<request>`: the data files the ingestion wrote (`data/outcomes/*.csv`,
  `data/reference/population.csv`) plus the review checklist, ready to be
  committed by a maintainer after inspection.
- `archive-<request>`: the raw documents under `archive/raw/`, their hashes,
  Wayback capture URLs and, for PDFs, extracted text.

Request file format:

```yaml
kind: ingest            # or: archive
source_id: uscourts-bankruptcy-f2
period: 2026-Q2         # YYYY-Qn for quarterly sources, YYYY-MM for monthly, omit for Census
# or, for a back series in one file:
# periods: [2024-01, 2024-02, 2024-03]
```

```yaml
kind: archive
label: research-pdfs
urls:
  - https://example.gov/report.pdf
```

Requests are idempotent: re-running one supersedes restated rows rather
than duplicating them. Delete a request file once its output is committed.
