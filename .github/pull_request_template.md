## What this changes

<!-- One or two sentences. For data changes, name the dataset and period. -->

## Type

- [ ] Data entry or correction (goes through the two-person review below)
- [ ] Schema or validator change
- [ ] Site or ingestion code
- [ ] Documentation

## Data review (delete if no data changed)

For every changed record: open the source link, find the page or table cited, confirm the value and the date.

- [ ] Every new or changed record has `source_id`, `source_url`, `retrieved_at`, `entered_by`
- [ ] Source documents are archived (archive_url or a hash under archive/raw)
- [ ] No value was taken from press or a tracker
- [ ] Market segment is correct (regulated sportsbook, prediction market, offshore or sweepstakes)
- [ ] Reviewer has checked each value against the source

## Validation

- [ ] `python3 scripts/validate.py` passes
- [ ] `python3 scripts/lint_dashes.py` passes
