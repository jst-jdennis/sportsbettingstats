# Design overview

Status: draft for review before code. Date: 2026-10-16.

This document set is the pre-code deliverable requested in the project brief:
the data model, the full source inventory with access method, cadence and
known reliability issues, the ingestion and review design, and the open
questions that need a decision from the project owner.

Files:

| File | Contents |
| --- | --- |
| `00-overview.md` | Naming recommendation, architecture decisions, phase plan |
| `01-data-model.md` | Every dataset, its fields, its schema, and the provenance model |
| `02-sources.md` | Every data source, access method, cadence, reliability, confidence that the data exists |
| `03-ingestion-and-review.md` | The Python ingestion layer and the contributor review workflow |
| `04-open-questions.md` | Decisions needed and facts not yet verified |

## 1. Name and domain

The brief asks for something neutral and institutional. The test applied
here: would a legislative staffer on either side of a sports betting vote
feel comfortable citing it by name in a committee memo, and does the name
survive the site covering prediction markets and sweepstakes as well as
sportsbooks?

Recommendation: **Wagering Policy Data Center**, short form "WPDC",
domain `wageringdata.org`.

Reasoning:

- "Wagering" is the term used in most state statutes and regulator names
  (New York "mobile sports wagering", Ohio "sports gaming", Tennessee
  "sports wagering"). It is broader than "sports betting" and covers event
  contracts without stretching.
- "Data Center" echoes the CDC STATE System and the Kaiser Family
  Foundation State Health Facts, both of which legislators already cite.
  It signals a reference, not a campaign.
- It contains no verb, no outcome word ("harm", "risk", "freedom") and no
  side.
- `.org` is the right TLD for a nonpartisan reference project.

Alternatives considered, in order of preference:

| Name | Domain idea | Why not first |
| --- | --- | --- |
| State Wagering Atlas | statewageringatlas.org | "Atlas" implies maps only; outcomes and research are half the site |
| US Betting Policy Tracker | bettingpolicytracker.org | "Betting" reads narrower than event contracts |
| Gambling Policy Data Center | gamblingpolicydata.org | "Gambling" is the word opponents use and operators avoid; it is read as a side by some audiences |

Domain availability was not checked from this environment. Please verify
before committing to a name. Nothing in the codebase will hard-code the
name; it lives in one site config value.

## 2. Architecture decisions

Each is recorded as a short ADR. The rule applied throughout: choose the
option that is correct for a citable reference, not the fastest to ship.

### ADR-1: Astro, fully static output

Astro over Next.js static export. Astro ships zero JavaScript by default,
which makes "works without JavaScript for core content" the default rather
than a discipline. Content collections give typed, build-time validated
access to the YAML and JSON data files. Deploy target is Cloudflare Pages
(free tier, global edge, no server). Vercel is interchangeable.

### ADR-2: Data as files, validated by schema on every build

- Tabular time series (handle, revenue, bankruptcy, helpline): CSV with a
  Frictionless Table Schema (`*.schema.json`) alongside each file.
  Frictionless is an open standard, has a mature Python validator, and the
  schema file is itself machine-readable documentation that a researcher
  can read without our tooling.
- Entity records (states, bills, papers, regulators, rubric): one YAML file
  per entity, validated against JSON Schema (Draft 2020-12). YAML is chosen
  for human review in pull requests.
- Derived and computed values (per capita rates, grades, pre/post
  windows) are never stored. They are computed at build time from primary
  records so that they cannot drift from their inputs. The build emits a
  `derived/` directory for inspection and export, and it is git-ignored.
- The build fails on any schema violation, any record missing a source, any
  source missing a retrieval date, and any numeric figure whose source is
  marked `status: unverified`.

### ADR-3: Provenance is a first-class table, not a column

Every record carries a `source_id` that resolves to a row in
`data/sources/sources.yaml`, plus `retrieved_at`, `retrieval_method` and
`entered_by`. Sources carry publisher, URL, archive URL (Wayback), license
and access method. Rendering a number without a resolvable source is a
build error. This is what lets every figure on the site link to its
primary source with the date retrieved.

### ADR-4: Market segment is an enum on every market-related record

`market_segment` takes one of `regulated_sportsbook`, `prediction_market`,
`offshore_or_sweepstakes`, `lottery_sports_product`, `daily_fantasy`. It
is required on legal status, revenue, enforcement actions, bills and
research key figures. Charts and tables never aggregate across segments
without labeling it. This is the structural enforcement of the "never
conflate" principle.

### ADR-5: Charts rendered to SVG at build time

Vega-Lite specifications compiled to static SVG at build with `vl-convert`
(no browser needed). Each chart is an `<img>` or inline SVG with a text
alternative and a data table beneath it, which satisfies WCAG and the
no-JavaScript requirement. The same spec renders a PNG for citation
screenshots and for the fact sheet PDF. Interactive hover is a progressive
enhancement layered on only where it adds value.

### ADR-6: Python ingestion layer, one module per source, no live fetch in the build

Ingestion runs separately from the site build (locally or in a scheduled
GitHub Action) and produces pull requests that change data files. The site
build never touches the network. Reasons: regulator sites go down, change
URLs, and publish PDFs; a build that depends on them is not reproducible.
A pull request per data change is also the review step the brief asks for.

### ADR-7: Fact sheets rendered from the same templates as pages

Fact sheet PDFs are generated at build from HTML templates using
WeasyPrint (Python, CSS Paged Media). One template, one data source, two
outputs. No separate PDF layout to keep in sync.

### ADR-8: Stable URLs and as-of dates

URL scheme: `/states/ok/`, `/states/ok/outcomes/`, `/bills/ok-2026-hb1047/`,
`/research/hollenbeck-larsen-proserpio-2024/`, `/report-cards/2026/`.
Every page shows an as-of date computed as the maximum `retrieved_at`
across the records it renders, plus the git commit hash. Report cards are
versioned by year and never silently recomputed in place; a change to the
rubric creates a new rubric version.

## 3. Phase plan, restated against this design

| Phase | Deliverables | Acceptance test |
| --- | --- | --- |
| 1 | Repo scaffold, all schemas, provenance model, ingestion framework with two working sources, state status map, complete profiles for Oklahoma plus two online states | `make validate` passes; map renders without JS; each profile figure links to a source with a date |
| 2 | Outcome time series (handle/revenue, bankruptcy, helpline, prevalence), pre/post windows, research library with revision log | Hollenbeck entry shows both the ATT figure and the event-study figure with version dates; NJ series spans pre and post June 2018 |
| 3 | Legislation tracker, report cards and published rubric | Grades regenerate identically from rubric plus data in CI; HB 1047 entry has vote counts and bill text link |
| 4 | CSV export on every table and chart, fact sheet PDF per state, citation widget | Each page has a `/data.csv` sibling and a `/factsheet.pdf` sibling |

Proposed Phase 1 states: Oklahoma (required), New Jersey (longest
post-PASPA monthly series, from June 2018, so the pre/post view is
meaningful), and Kansas (an Oklahoma neighbor, online launch September
2022, monthly reports published by the Kansas Lottery). Kansas can be swapped
for Pennsylvania or Ohio if a larger market is preferred; see
`04-open-questions.md`.

## 4. Writing rules enforced by lint

- No em dashes or en dashes in copy. A build-time lint scans content and
  templates for U+2014 and U+2013 and fails.
- No figure without a source. Enforced by the template layer: the only way
  to print a number from data is through a `<Figure>` component that
  requires a source reference.
- Limitation notes are data, not prose. Each dataset schema carries a
  `limitations` field that renders on every page where the dataset appears.
