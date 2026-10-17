# Source inventory

Status: draft for review. Date: 2026-10-16.

Each source lists: what it provides, access method, update cadence, known
reliability issues, tier (per `01-data-model.md` section 1.3), and a
confidence rating that the data exists in usable form:

- **Confirmed**: the publication is known and its format is understood.
- **Likely**: the publisher is known to produce it; format or coverage
  not yet inspected from this environment.
- **Uncertain**: existence or public availability is in doubt. Flagged
  for the project owner.

Where a claim below rests on a secondary summary rather than the primary
page, it is marked "(secondary)". Those items get verified during Phase 1
before any record is marked `verified`.

## A. Legal status, governance, tax, protections

### A1. State statutes, regulations and ballot measures

- Provides: authorizing statute, effective dates, legal age, tax rate and
  basis, promo deduction rules, advertising rules, self-exclusion rules.
- Access: `manual_entry` from state legislature code sites and regulator
  rule pages; `pdf` for administrative codes.
- Cadence: irregular (session-driven).
- Reliability: statutes and regulations are authoritative but headline
  tax rates in press are frequently wrong about the basis (gross vs
  adjusted revenue) and about promo deductibility. Every tax record must
  cite the code section.
- Tier: primary. Confidence: confirmed.

### A2. State regulator websites (39 states plus DC)

- Provides: licensee lists, launch dates, self-exclusion program pages,
  advertising guidance, and in most states the revenue reports (see B1).
- Access: mix of `html_table`, `pdf`, `xlsx`. No state offers a documented
  public API for sports wagering data.
- Cadence: monthly for revenue; irregular otherwise.
- Reliability: URL churn is the main problem. Several regulators move or
  rename report pages yearly. Mitigation: archive every retrieved document
  to the Wayback Machine and store the archive URL.
- Tier: primary. Confidence: confirmed in aggregate; per-state inventory is
  a Phase 1 deliverable (`data/sources/sources.yaml` will carry one entry
  per regulator with the exact report URL pattern).

### A3. Tribal-state gaming compacts and Department of the Interior notices

- Provides: authority and scope for tribal sports wagering (relevant to
  Oklahoma's status and to several Phase 2 states).
- Access: `pdf` from the Bureau of Indian Affairs compact list and
  Federal Register notices.
- Cadence: irregular.
- Reliability: compacts are authoritative; their operational status (is
  wagering actually offered) is not in the compact and needs regulator or
  tribal gaming agency confirmation.
- Tier: primary. Confidence: confirmed.

### A4. Secondary cross-checks for legal status

American Gaming Association state tracker, Legal Sports Report, Sports
Handle, and the Tax Foundation's sports betting tax tables. Used only to
detect omissions and to find primary citations. Tier: tertiary (AGA is an
industry association; its tracker is well maintained but not a citable
source for this site's standards). Confidence: confirmed.

## B. Outcome series

### B1. State regulator monthly handle and revenue reports

- Provides: handle, gross revenue, adjusted revenue, promotional
  deductions, tax paid, by channel and sometimes by operator.
- Access: varies by state. Known examples to be confirmed in Phase 1:
  New Jersey Division of Gaming Enforcement monthly press release and
  PDF tables; Pennsylvania Gaming Control Board monthly revenue reports
  (xlsx and pdf); New York State Gaming Commission weekly mobile sports
  wagering xlsx; Kansas Lottery monthly sports wagering revenue page;
  Ohio Casino Control Commission monthly PDF; Illinois Gaming Board
  monthly PDF; Nevada Gaming Control Board monthly revenue report (PDF,
  sports pool line within a larger report).
- Cadence: monthly, typically 10 to 25 days after month end. Nevada and
  a few others lag further.
- Reliability issues, all known and all must be modeled:
  - "Revenue" definitions differ (gross, adjusted, taxable). Captured in
    `revenue_definition`.
  - Prior months are restated when operators correct filings; the
    `is_revised` flag and `superseded` status handle this.
  - Fiscal versus calendar months (some states report fiscal periods).
  - Several states report retail and online combined for some periods
    and separately for others.
  - PDFs change layout without notice, which breaks parsers. Each
    regulator module has a layout fingerprint and fails loudly instead
    of guessing.
- Tier: primary. Confidence: confirmed for the states named; likely for
  the remainder.
- Report pages confirmed on 2026-10-17 for the Phase 6 states (the
  module for each state records the file layout it was written against):
  - Pennsylvania: Gaming Control Board revenue pages by fiscal year
    (`gamingcontrolboard.pa.gov/news-and-transparency/revenue/sports-wagering-fy-YYYYYYYY`),
    each with a monthly sports wagering summary in xlsx and pdf.
  - New York: Gaming Commission monthly and weekly statewide mobile
    sports wagering reports (`gaming.ny.gov/system/files/documents/<year>/<month>/monthly-mobile-sports-wagering-report-statewide.pdf`),
    reporting handle and gross gaming revenue on a cash basis by month
    of the April to March fiscal year.
  - Michigan: Gaming Control Board internet sports betting and retail
    sports betting revenue tables, linked from the monthly press release.
  - Kansas: Lottery publications page, "Sports Wagering Monthly Revenues"
    PDF (`kslottery.com/publications/sports-monthly-revenues/`).
  - Ohio: Casino Control Commission revenue reports page, one xlsx per
    year and one pdf per month (`casinocontrol.ohio.gov/about/revenue-reports/04-revenue-reports`),
    gross receipts, winnings paid, voided wagers and promotional credits
    by proprietor, online and retail.
  - Illinois: Gaming Board sports wagering reports page
    (`igb.illinois.gov/sports-wagering/sports-reports.html`), monthly pdf
    and csv by licensee; figures are due the last day of the following
    month, so the series lags two months.

### B2. US Courts, Bankruptcy Filings Statistics (Table F-2 and F-5A)

- Provides: business and nonbusiness filings by chapter and by federal
  judicial district (F-2) and by district and county (F-5A), both as
  quarterly counts and as twelve-month totals ending each quarter.
- Access: `bulk_download` (xlsx and pdf per quarter from uscourts.gov).
  There is also a public dashboard with data back to 2007.
- Cadence: quarterly, roughly four to six weeks after quarter end.
- Reliability: authoritative and stable in format. Not monthly, which
  limits short-window event analysis. District to state mapping is exact.
  The series has large exogenous breaks (2005 BAPCPA, the 2020 to 2021
  pandemic trough) that must be annotated on charts.
- Tier: primary. Confidence: confirmed.

### B3. American Bankruptcy Institute and Epiq monthly statistics

- Provides: monthly filings by state, which would give a monthly series
  instead of quarterly.
- Access: ABI publishes headline monthly press releases publicly; the
  state-level monthly tables come from Epiq AACER and appear to require
  a subscription.
- Cadence: monthly.
- Reliability: Epiq counts can differ slightly from US Courts counts
  because of timing of case entry.
- Tier: secondary. Confidence: **uncertain** that state-level monthly
  data is available without a paid subscription. Recommendation: use US
  Courts quarterly data as the published series; treat ABI monthly as a
  possible enhancement if a data-sharing arrangement can be made.

### B4. NCPG 1-800-GAMBLER helpline volume

- Provides: contacts to the national helpline number.
- Access: NCPG publishes network-wide aggregates in fact sheets and
  annual reports. A public state-by-state time series was **not found**.
  NCPG has stated it is standardizing data collection across its 27
  contact centers.
- Cadence: annual aggregates; no known monthly public state series.
- Reliability: the network is a federation; counting rules differ by
  center.
- Tier: primary (for national totals). Confidence: **uncertain** at the
  state level. Recommendation: request state-level data from NCPG
  directly and, in parallel, use B5.

### B5. State problem gambling councils and state agencies (helpline reports)

- Provides: state helpline contacts, often monthly, sometimes with
  caller demographics and gambling type.
- Access: `pdf` annual reports and, in some states, monthly reports.
  Known examples: Council on Compulsive Gambling of Pennsylvania annual
  and monthly helpline reports; Council on Compulsive Gambling of New
  Jersey; Ohio for Responsible Gambling; Massachusetts Gaming
  Commission's research pages; Kansas Department for Aging and
  Disability Services problem gambling program reports.
- Cadence: monthly to annual, varies.
- Reliability: counting rules differ (unique callers vs contacts; whether
  out-of-state calls are included). The `counting_rule` column is
  mandatory for this reason, and series are not compared across states
  without that caveat rendered.
- Tier: primary. Confidence: confirmed for Pennsylvania (secondary);
  likely for the others; coverage will be incomplete and will be shown
  as such.

### B6. State prevalence studies

- Provides: problem gambling and at-risk rates from state-commissioned
  surveys.
- Access: `pdf`, `manual_entry`. Studies are one-off or periodic (for
  example Massachusetts SEIGMA, Ohio's periodic prevalence surveys,
  Oklahoma's Department of Mental Health and Substance Abuse Services
  studies, Connecticut, Maryland, New Jersey Rutgers studies).
- Cadence: irregular, often every 3 to 7 years.
- Reliability: instruments differ (PGSI, NODS, SOGS, DSM-5); not
  comparable across instruments. Modeled as study records, not a series.
- Tier: primary. Confidence: confirmed that studies exist for many
  states; which states have one is itself a tracked fact and a report card
  criterion.

### B7. Census Bureau population estimates

- Provides: annual state population for per capita denominators.
- Access: `api` (Census Population Estimates API) or `bulk_download`.
- Cadence: annual vintage.
- Reliability: vintages revise prior years; the vintage used is recorded.
- Tier: primary. Confidence: confirmed.

## C. Problem gambling funding

### C1. NAADGS (National Association of Administrators for Disordered Gambling Services) national survey

- Provides: public problem gambling funding by state and fiscal year,
  with per capita figures. Last known full survey published May 2022
  with a budget update for FY2023 (secondary).
- Access: `pdf`, `manual_entry`.
- Cadence: irregular, roughly every two to three years with interim
  budget updates.
- Reliability: self-reported by state administrators; some states report
  appropriations, others expenditures. Store which one and show it.
- Tier: secondary (aggregates state budgets). Confidence: confirmed that
  surveys exist; **uncertain** whether an edition newer than FY2023 has
  been published. Verify on naadgs.org in Phase 1.

### C2. State appropriations acts and agency budgets

- Provides: the primary record of what a state actually funds.
- Access: `manual_entry` from appropriation bills and agency budget
  documents.
- Cadence: annual.
- Reliability: authoritative but laborious; use C1 to prioritize and C2
  to verify the Phase 1 states and any state whose grade depends on it.
- Tier: primary. Confidence: confirmed.

## D. Prediction markets

### D1. CFTC (Commodity Futures Trading Commission) records

- Provides: designated contract market list, event contract
  self-certifications, rulemaking dockets and comment files on event
  contracts, enforcement.
- Access: `html_table`, `pdf`, some `bulk_download` of filings.
- Cadence: irregular.
- Reliability: authoritative for federal status. Tells you nothing about
  state-by-state availability.
- Tier: primary. Confidence: confirmed.

### D2. State regulator and attorney general actions

- Provides: cease and desist letters, lawsuits, advisory opinions against
  prediction market platforms.
- Access: `pdf`, `manual_entry` from regulator press rooms and AG sites.
- Cadence: irregular; active area with more than twenty states reported
  to have taken some action (secondary; must be confirmed state by state).
- Reliability: the letters are primary and usually public; whether a
  platform actually geofences a state after a letter is not reliably
  documented anywhere and is recorded as `unknown` unless confirmed.
- Tier: primary. Confidence: confirmed that actions exist; per-state
  completeness will be built up over time and the site will say so.

### D3. Federal court dockets (PACER, CourtListener, circuit opinion archives)

- Provides: case status and rulings in the Kalshi and related litigation.
  As of this writing (secondary summaries, to be verified against the
  opinions): Third Circuit affirmed a preliminary injunction for Kalshi
  against New Jersey on 2026-04-06; Ninth Circuit ruled against Kalshi
  in the Nevada case on 2026-08-28; Sixth Circuit ruled against Kalshi
  in the Ohio and Tennessee cases on 2026-09-25; a petition for
  certiorari from New Jersey was filed 2026-09-02. All are rulings on
  preliminary relief, not final judgments.
- Access: CourtListener `api` (free, with RECAP docket mirrors) and the
  circuits' published opinion PDFs. PACER has per-page fees.
- Cadence: irregular.
- Reliability: CourtListener coverage of dockets depends on RECAP
  uploads; opinions themselves are complete.
- Tier: primary. Confidence: confirmed.

### D4. Platform disclosures

- Provides: platform statements on which states they serve, volume
  figures.
- Access: `manual_entry`.
- Reliability: self-reported marketing material. Used only for the
  `operating_platforms` as-of record, labeled as platform-stated.
- Tier: tertiary for volume; primary only for the platform's own stated
  availability. Confidence: confirmed.

## E. Legislation

### E1. LegiScan API

- Provides: bills, actions, sponsors, roll calls, bill text links for all
  50 states. Free public key allows 30,000 queries per month and includes
  roll call and sponsor endpoints (secondary; confirm on legiscan.com
  pricing page). Paid tiers add weekly bulk datasets.
- Access: `api`.
- Cadence: near daily during sessions.
- Reliability: good coverage; vote tallies are reliable; summaries are
  machine-generated and are not used as our summary text.
- Tier: secondary (aggregates legislature sites). Confidence: confirmed.

### E2. Open States API v3 and bulk data

- Provides: similar coverage, public domain bulk data, free key.
- Access: `api`, `bulk_download`.
- Reliability: coverage of votes varies by state; keyword search is less
  precise than LegiScan's. Used as a cross-check and fallback.
- Tier: secondary. Confidence: confirmed.

### E3. State legislature websites and journals

- Provides: the authoritative vote record, bill text, fiscal notes. For
  Oklahoma: oklegislature.gov bill pages and the Senate Journal.
- Access: `html_table`, `pdf`, `manual_entry`.
- Reliability: authoritative. Every `verified` vote record cites the
  journal or official roll call page, not only an aggregator.
- Tier: primary. Confidence: confirmed.

## F. Research library

### F1. Paper repositories: SSRN, NBER, arXiv, journal sites, author pages

- Provides: paper versions with dates.
- Access: `manual_entry` plus a local archive of each version PDF with its
  SHA-256 hash (NBER PDFs are stable; SSRN replaces the file in place when
  authors upload a new version, which is exactly why we hash and archive).
- Cadence: irregular.
- Reliability: version dating on SSRN is author-controlled and sometimes
  missing from the PDF. Where the PDF carries no date, the archive
  capture date is recorded as the earliest known date for that version.
- Tier: primary. Confidence: confirmed.

Initial entries:

1. Hollenbeck, Larsen, Proserpio, "The Financial Consequences of Legalized
   Sports Gambling." Working paper, first circulated 2024; May 2025 draft
   hosted at UCLA Anderson. Versions and figures to be recorded per
   `01-data-model.md` section 6. Policy citations: Minnesota Senate
   Finance Committee, January 2025.
2. Baker, Balthrop, Johnson, Kotter, Pisciotta, "Gambling Away Stability:
   Sports Betting's Impact on Vulnerable Households." NBER Working Paper
   33108 (November 2024); listed as published in the Journal of Financial
   Economics, vol. 183 (2026) (secondary; confirm DOI). Replication data
   on Mendeley Data.

### F2. Legislative testimony archives

- Provides: the record of which papers and figures were cited to
  legislators, which is itself useful to the audience.
- Access: `manual_entry`.
- Tier: primary (for the fact of the citation). Confidence: confirmed.

## G. Summary of flagged uncertainties

| Item | Status | Proposed handling |
| --- | --- | --- |
| State-level helpline volume from NCPG | Uncertain | Ask NCPG; rely on state councils; show coverage gaps honestly |
| Monthly state bankruptcy counts (ABI/Epiq) | Uncertain, likely paid | Publish US Courts quarterly; pursue ABI access separately |
| NAADGS survey newer than FY2023 | Uncertain | Verify in Phase 1; use state budgets for Phase 1 states |
| Platform geofencing by state after enforcement letters | Not systematically documented | Record `unknown` unless confirmed by the regulator or the platform |
| Complete per-state enforcement action list for prediction markets | Partial | Build incrementally; display count of states reviewed |
| Exact format and URL stability of each of 39 regulators' reports | Known in general, not inspected one by one | Phase 1 inventory task with one `sources.yaml` entry per regulator |
| Hollenbeck version history | Both headline figures confirmed in secondary sources; PDFs not yet fetched from this environment | Fetch, hash and archive each version in Phase 2 before publishing the entry |
