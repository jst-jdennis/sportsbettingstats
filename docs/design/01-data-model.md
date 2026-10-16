# Data model

Status: draft for review. Date: 2026-10-16.

Conventions used in this document:

- `pk` marks the primary key. Composite keys are listed in order.
- `src` means the record carries the standard provenance block (section 1).
- Enumerations are closed. Adding a value is a schema change reviewed in a
  pull request.
- Dates are ISO 8601. Money is integer US dollars unless the column name
  ends in `_cents`. Rates are decimals (0.13 not 13).
- Nothing derived is stored. Per capita values, grades, growth rates and
  pre/post windows are computed at build from the records below.

Directory layout:

```
data/
  sources/sources.yaml            registry of every source (section 1)
  reference/states.csv            FIPS, names, abbreviations
  reference/population.csv        Census annual estimates, for per capita
  reference/districts.csv         federal judicial district to state map
  states/<st>/profile.yaml        legal status, regulator, age, tax, protections
  states/<st>/prediction_markets.yaml
  states/<st>/pg_funding.yaml
  outcomes/handle_revenue.csv
  outcomes/bankruptcy.csv
  outcomes/helpline.csv
  outcomes/prevalence_studies.yaml
  research/papers/<slug>.yaml
  legislation/bills/<slug>.yaml
  report_cards/rubric/<version>.yaml
schemas/
  *.schema.json                   JSON Schema for YAML entities
  *.tableschema.json              Frictionless Table Schema for CSVs
```

## 1. Provenance model

### 1.1 `sources.yaml` (registry)

| Field | Type | Notes |
| --- | --- | --- |
| `source_id` (pk) | slug | e.g. `njdge-monthly-sports-wagering` |
| `publisher` | string | Legal name of the publishing body |
| `publisher_type` | enum | `state_regulator`, `state_agency`, `federal_agency`, `court`, `legislature`, `nonprofit`, `academic`, `industry_association`, `news` |
| `title` | string | |
| `url` | url | Canonical landing page |
| `access_method` | enum | `api`, `bulk_download`, `html_table`, `pdf`, `xlsx`, `manual_entry`, `foia_request` |
| `update_cadence` | enum | `weekly`, `monthly`, `quarterly`, `annual`, `irregular`, `one_time` |
| `license` | string | Public domain, state terms, or `unknown` |
| `reliability_notes` | text | Known format changes, revisions, gaps |
| `tier` | enum | `primary`, `secondary`, `tertiary` (see 1.3) |

### 1.2 Provenance block (embedded in every record)

| Field | Type | Notes |
| --- | --- | --- |
| `source_id` | ref | Must resolve to `sources.yaml` |
| `source_url` | url | Exact document or page, not the landing page |
| `archive_url` | url | Wayback Machine or local `archive/` copy hash; required for PDFs and HTML, optional for APIs |
| `retrieved_at` | date | |
| `retrieval_method` | enum | same values as `access_method` |
| `transform` | string | Short description, e.g. "sum of retail rows; promo deductions excluded" |
| `entered_by` | string | GitHub handle or ingestion module name |
| `reviewed_by` | string | GitHub handle; required before `status` can be `verified` |
| `status` | enum | `verified`, `pending_review`, `unverified`, `disputed`, `superseded` |
| `notes` | text | Free text, shown on hover and in CSV export |

Build rules: a record with `status: unverified` or `pending_review` renders
with a visible badge and is excluded from report card scoring and from
headline figures. `superseded` records remain in the files (for the
revision history) but do not render.

### 1.3 Source tiers

- `primary`: the body that produces the number (a regulator's revenue
  report, a court's docket, a paper's PDF).
- `secondary`: a body that aggregates primary data with a documented
  method (US Courts tables are primary for filings; the American
  Bankruptcy Institute's state rollups are secondary).
- `tertiary`: trade press and trackers. Allowed only as a lead to find a
  primary source, never as the cited source for a figure. The schema
  enforces this: a `Figure` with a tertiary source fails validation.

## 2. Reference data

### 2.1 `states.csv`

`fips` (pk), `abbr`, `name`, `region` (Census region), `has_tribal_gaming_compacts` (bool, src).

### 2.2 `population.csv`

`fips`, `year` (pk together), `population`, src (Census Vintage estimates).
Used for all per capita and per 100,000 figures. The vintage used is
shown wherever a per capita figure appears.

### 2.3 `districts.csv`

`district_code` (pk), `fips`. Maps the 94 federal judicial districts to
states, because US Courts publishes filings by district. Every district is
within one state, so the sum is exact.

## 3. State profile (`states/<st>/profile.yaml`)

One document per state, validated by `state_profile.schema.json`.

### 3.1 Legal status

`legal_status` is a list of channel records, not a single value, because
a state can be retail-legal from one date and online-legal from another,
and online can be limited in scope.

| Field | Type | Notes |
| --- | --- | --- |
| `market_segment` | enum | Always `regulated_sportsbook` here; other segments live in their own sections |
| `channel` | enum | `retail`, `online` |
| `scope` | enum | `statewide`, `on_premises_only` (e.g. Mississippi mobile), `tribal_lands_only`, `lottery_kiosk` |
| `status` | enum | `not_authorized`, `authorized_not_launched`, `live`, `suspended`, `repealed` |
| `authorized_on` | date | Statute or ballot measure effective date |
| `launched_on` | date | First legal wager accepted |
| `authority` | object | `type` (`statute`, `ballot_measure`, `compact`, `regulation`), `citation`, `url` |
| `operator_model` | enum | `commercial`, `lottery_monopoly`, `tribal_exclusive`, `mixed` |
| src | | |

The headline status shown on the map (none / retail only / online / both)
is derived at build from this list and never stored.

### 3.2 Governance

`regulators`: list of `{name, url, type: enum(gaming_commission, lottery, racing_commission, tribal_gaming_agency, attorney_general), role: enum(licensing, enforcement, revenue_reporting), src}`.

### 3.3 Legal age

`legal_age: {age: int, authority_citation, src}`. Some states differ by
venue (tribal 18, commercial 21); model as a list with `scope` if needed.

### 3.4 Tax structure

Tax is a list because many states tax channels differently and some use
tiers or per-wager surcharges.

| Field | Type | Notes |
| --- | --- | --- |
| `channel` | enum | `retail`, `online`, `all` |
| `basis` | enum | `gross_gaming_revenue`, `adjusted_gross_revenue`, `handle`, `per_wager` |
| `rate` | decimal | For flat rates |
| `tiers` | list | `{threshold_from, threshold_to, rate}` for progressive structures |
| `per_wager_fee_cents` | int | For surcharges such as Illinois's 2025 per-wager fee |
| `promo_deduction_rule` | text | Whether and how promotional credits are deductible; this is where headline rates become misleading |
| `effective_from`, `effective_to` | date | Rate history is retained as separate rows |
| `destination` | list | `{fund_name, share}` where published |
| src | | |

### 3.5 Consumer protections

Each item below is its own object with its own `src` so that a report card
criterion maps to exactly one field.

| Key | Fields |
| --- | --- |
| `self_exclusion` | `program_type` (statewide_registry, operator_only, both), `administered_by`, `durations` (list, e.g. 1y, 5y, lifetime), `covers` (list of segments and venues), `enrollment_methods`, `url` |
| `deposit_limits` | `mandatory_default` (bool), `player_set_required_at_signup` (bool), `cooling_off_on_increase_hours`, `statutory_cap` |
| `advertising` | list of rules, each `{rule_type: enum(no_college_campus, no_under_21_targeting, no_risk_free_language, responsible_gambling_message_required, time_of_day_restriction, whistle_to_whistle, affiliate_restriction, other), text, authority_citation}` |
| `credit_card_deposits` | `allowed` (bool) |
| `affordability_checks` | `required` (bool), `threshold_rule` |
| `cooling_off_and_timeouts` | `available` (bool), `mandatory` (bool) |
| `rg_message_requirements` | `helpline_number_required` (bool), `required_number` |

### 3.6 Problem gambling funding (`states/<st>/pg_funding.yaml`)

List of fiscal-year records: `fiscal_year`, `amount_usd`, `funding_mechanism`
(enum: `statutory_earmark_pct_revenue`, `appropriation`, `license_fee`,
`none`), `mechanism_text`, `administering_agency`, `includes_treatment`,
`includes_prevention`, `includes_research`, src. Per capita is computed
against `population.csv` for the same year.

## 4. Prediction markets (`states/<st>/prediction_markets.yaml`)

Separate file and segment by design.

| Section | Fields |
| --- | --- |
| `operating_platforms` | list of `{platform, offers_sports_contracts (bool), offers_in_state (enum: yes, no, geofenced_out, unknown), as_of, src}` |
| `state_actions` | list of `{action_type: enum(cease_and_desist, lawsuit_filed, subpoena, legislation, advisory_opinion, settlement), date, issuing_body, target, summary, document_url, src}` |
| `litigation` | list of `{case_name, court, docket, filed_on, status: enum(pending, preliminary_injunction_granted, preliminary_injunction_denied, appeal_pending, decided, dismissed, settled), latest_ruling_date, latest_ruling_summary, src}` |

Litigation summaries state the procedural posture explicitly (preliminary
relief versus final judgment) because that distinction has been the most
commonly misreported fact in this area.

## 5. Outcome time series

### 5.1 `handle_revenue.csv`

| Column | Type | Notes |
| --- | --- | --- |
| `fips`, `period_start`, `period_end`, `channel`, `market_segment` | pk | Period is usually a calendar month; some states report fiscal months or weeks |
| `handle_usd` | int | Total amount wagered |
| `gross_revenue_usd` | int | Handle minus winnings paid, before promo deductions. Nullable if the state publishes only one revenue line |
| `adjusted_revenue_usd` | int | After deductions the state allows; the taxable base in most states |
| `promo_deductions_usd` | int | Nullable |
| `state_tax_usd` | int | Tax or revenue share received by the state |
| `revenue_definition` | text | Verbatim label the regulator uses, because "revenue" means different things across states |
| `is_revised` | bool | True when the regulator restated a prior period |
| src columns | | `source_id`, `source_url`, `archive_url`, `retrieved_at`, `status`, `entered_by`, `reviewed_by`, `notes` |

Limitations field on the schema (rendered with every chart): figures are
operator-reported to regulators; definitions of revenue differ by state;
handle includes re-wagered winnings; monthly figures reflect event
calendars and are not seasonally adjusted.

### 5.2 `bankruptcy.csv`

| Column | Type | Notes |
| --- | --- | --- |
| `fips`, `period_start`, `period_end`, `chapter` | pk | `chapter` in `7`, `13`, `11`, `all_nonbusiness` |
| `filings` | int | Nonbusiness filings, summed from district rows |
| `measure` | enum | `quarter`, `twelve_months_ending` (US Courts publishes both) |
| src | | |

Per 100,000 is computed against `population.csv`. Limitations: filings
respond to many factors (medical debt, housing, policy changes such as the
2005 BAPCPA and the 2020 to 2021 pandemic trough); population-level
changes cannot be attributed to any single cause from this table; the
peer-reviewed estimates in the research library use individual credit
records and control groups, which these aggregates do not.

### 5.3 `helpline.csv`

| Column | Type | Notes |
| --- | --- | --- |
| `fips`, `period_start`, `period_end`, `contact_type` | pk | `contact_type` in `call`, `text`, `chat`, `all` |
| `contacts` | int | |
| `operator` | string | State council or contact center name |
| `counting_rule` | text | Whether out-of-state and wrong-number contacts are included; whether the series counts unique callers |
| src | | |

Limitations: helpline volume responds to advertising of the number
itself (it rises when operators are required to print it), so it is a
measure of help-seeking and awareness, not prevalence.

### 5.4 `prevalence_studies.yaml`

List of study records, not a time series, because methods differ.
Schema: `schemas/prevalence_studies.schema.json`.

`study_id` (pk), `fips`, `title`, `authors`, `commissioned_by`,
`conducted_by`, `published_at`, `fieldwork_start`, `fieldwork_end`,
`instrument` (enum: `PGSI`, `DSM-IV-NODS`, `DSM-5`, `SOGS`, `BBGS`, `other`),
`instrument_note` (thresholds), `sample_size`, `population`, `mode`,
`margin_of_error_pct_points`, `rates[]` (each with `measure`, the report's
own `definition`, `value_pct`, optional confidence interval, `denominator`
and its own provenance block with page reference), `report_url`,
`comparability_note`, `limitations`, src.

Rates are stored as published and never recomputed; a study that reports
"high risk" under a nine-item screen and one that reports "problem gambling"
under PGSI 8+ are different measures and are stored under different
`measure` and `definition` values.

Limitations: instruments and thresholds differ; rates are not comparable
across studies that use different instruments; the field renders a
"not comparable" marker when two studies on the same page use different
instruments.

## 6. Research library (`research/papers/<slug>.yaml`)

| Field | Notes |
| --- | --- |
| `slug` (pk) | `authors-year`, e.g. `hollenbeck-larsen-proserpio-2024` |
| `title`, `authors` (list), `year_first_circulated` | |
| `publication_status` | enum: `working_paper`, `under_review`, `forthcoming`, `published` |
| `venue`, `doi`, `canonical_url` | |
| `data_used`, `design` | Short method description: data source, identification strategy, unit of analysis, sample period |
| `plain_language_summary` | One paragraph, written to the style guide (no advocacy) |
| `market_segment` | Which segment the paper studies |
| `unit_of_effect` | enum: `population_average`, `bettor_level`, `household_level`. Rendered as a limitation line because population-wide averages are routinely misread as per-bettor effects |
| `versions` | list, see below |
| `key_figures` | list, see below |
| `citations_in_policy` | optional list of legislative testimony or committee documents that cite the paper, with src |

`versions[]`: `{version_label, date, url, archive_url, sha256, changes_summary, src}`.

`key_figures[]`: `{figure_id, description, value_text, specification
(e.g. "ATT, Table 4" or "event study, years 3 to 4"), version_label (which
version it appears in), status: enum(current, superseded, withdrawn),
superseded_by (figure_id), page_or_table, outcome_domain, value_numeric,
value_unit, range_low, range_high, src}`. `value_text` is the figure as the
paper states it. `value_numeric` and `value_unit` (enum: `percent_change`,
`percentage_points`, `per_100k`, `usd`, `index_points`) are the same figure
as a signed number, so that the outcomes page can chart estimates from
different papers on one axis; they are null until read from the paper.
`outcome_domain` groups figures by the outcome measured (bankruptcy, credit
score, saving and investing, help-seeking, intimate partner violence and so
on). Only current figures whose provenance is not `unverified` are charted.

This structure records two different kinds of change explicitly:

1. A number that changed between drafts (same `figure_id`, two versions,
   old one `superseded`).
2. Two numbers that coexist in one draft under different specifications
   (two `figure_id`s, same version). The Hollenbeck case shows both kinds:
   the October 2024 draft states an average effect of about 10 percent and
   an event-study peak of 25 to 30 percent at three to four years; the
   January 2025 slides show 27 percent; the April 2025 draft reports about
   10 percent and no longer states the 25 to 30 percent figure; and the
   28 percent quoted in 2024 press coverage appears in neither archived
   draft. The library shows all of this, with dates and document hashes,
   rather than pick one.

A `revision_log` is rendered from `versions[]` and `key_figures[]`; it is
not a free-text field.

## 7. Legislation (`legislation/bills/<slug>.yaml`)

| Field | Notes |
| --- | --- |
| `slug` (pk) | `<st>-<session>-<number>`, e.g. `ok-2026-hb1047` |
| `fips`, `session`, `bill_number`, `title` | |
| `market_segment` | What the bill would authorize or restrict |
| `summary` | Plain language, no advocacy |
| `sponsors` | list of `{name, chamber, party, role: primary or cosponsor}` |
| `status` | enum: `introduced`, `in_committee`, `passed_first_chamber`, `passed_both`, `enacted`, `vetoed`, `failed_floor_vote`, `died_in_committee`, `withdrawn` |
| `actions` | list of `{date, chamber, action_text, src}` |
| `votes` | list of `{date, chamber, motion, yeas, nays, excused, result, rollcall_url, src}` |
| `text_url`, `legislature_page_url` | |
| `fiscal_note_url`, `fiscal_estimate_text` | Where a fiscal note exists; conflicting revenue estimates in press are recorded as `notes`, not as data |
| `related_bills` | list of slugs |
| `external_ids` | `{legiscan_bill_id, openstates_id}` for sync |
| src | |

First entry: Oklahoma HB 1047, 2026 session, failed Senate floor vote
27 to 21 on 2026-04-22 (to be confirmed against the Oklahoma Senate
journal before the record is marked `verified`; press accounts agree on
the tally and date).

## 8. Report cards (`report_cards/rubric/<version>.yaml`)

| Field | Notes |
| --- | --- |
| `version` (pk) | e.g. `2026.1` |
| `effective_from` | |
| `criteria` | list of `{criterion_id, title, data_path (JSON pointer into the state profile), scoring: list of {condition, points}, max_points, rationale, evidence_basis (citations for why this criterion matters)}` |
| `grade_bands` | list of `{min_pct, grade}` |
| `not_applicable_rule` | How states with no legal market are handled (recommendation: scored only on the criteria that apply to any state, such as funding and prevalence research, and shown with an explicit "no regulated market" label rather than an F) |

Grades are computed at build by applying `criteria[].scoring` to the state
profile. The computation is deterministic and a CI test recomputes every
grade and fails if any differs from the rendered value. The rubric page
shows, for each state and criterion, the data value, the source and the
points awarded.

## 9. Build-time validation summary

| Check | Fails build |
| --- | --- |
| Schema validation of every file | yes |
| Every `source_id` resolves | yes |
| Every record has `retrieved_at` and `status` | yes |
| Tertiary source used as a figure source | yes |
| `verified` without `reviewed_by` | yes |
| Em dash or en dash in content | yes |
| Grade recomputation mismatch | yes |
| Period overlap within a time series key | yes |
| Per capita denominator year missing | yes |
| Record older than source cadence times three | warning, rendered as "may be stale" |
