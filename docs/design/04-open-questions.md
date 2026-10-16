# Open questions and decisions needed

Status: draft for review. Date: 2026-10-16.

## Decisions for the project owner

1. **Name and domain.** Recommendation is Wagering Policy Data Center,
   `wageringdata.org`. Alternatives in `00-overview.md`. Domain
   availability not checked from this environment.

2. **Phase 1 online states.** Recommendation: New Jersey and Kansas.
   New Jersey gives the longest monthly series; Kansas is an Oklahoma
   neighbor with a 2022 online launch and a lottery-published monthly
   report. Alternatives: Pennsylvania (large market, good xlsx reports)
   or Ohio (clean January 2023 launch, good for a pre/post illustration).

3. **Report card handling of states with no regulated market.** Options:
   (a) grade only on criteria that apply to any state, such as treatment
   funding and prevalence research, and label "no regulated market";
   (b) show "not graded". Recommendation is (a), because the site's
   audience includes legislators in those states and funding and research
   are their levers today. This choice is visible policy and should be
   yours.

4. **Licensing.** Data under CC0 or CC BY 4.0; code under the repository's
   existing license. Recommendation: CC BY 4.0 for data so that
   downstream users cite the site, which serves the "become the thing
   people cite" goal. The repository currently ships a GPL-family LICENSE
   file at the root; confirm whether that is intended for the code.

5. **Hosting account.** Cloudflare Pages is recommended. The session has a
   Cloudflare connector configured but not authorized; deployment setup
   is out of scope until Phase 1 is accepted.

## Facts to verify before any record is marked verified

These were established from secondary sources during design and must be
confirmed against the primary document, archived, and cited.

| Claim | Secondary basis | Primary to check |
| --- | --- | --- |
| Oklahoma HB 1047 failed in the Senate 27 to 21 on 2026-04-22 | Multiple press accounts agree | Oklahoma Senate Journal and the bill's official vote record |
| Hollenbeck May 2025 draft: ATT about 10 percent (Table 4); event study 25 to 30 percent at years 3 to 4; earlier materials headlined 27 to 28 percent | Search summaries quoting the PDF and the January 2025 slides | The UCLA-hosted PDF, the Minnesota Senate archive copy, and any SSRN version; hash and archive each |
| Baker et al. published in Journal of Financial Economics vol. 183 (2026) | NBER listing | Journal page and DOI |
| Third Circuit (2026-04-06), Ninth Circuit (2026-08-28) and Sixth Circuit (2026-09-25) rulings and their dispositions | Law firm and press summaries | The published opinions on the circuits' sites |
| New Jersey certiorari petition filed 2026-09-02, No. 26-299 | One tracker site | Supreme Court docket |
| LegiScan public tier: 30,000 queries per month including roll calls | Third-party API directories | legiscan.com pricing page |
| NAADGS FY2023 totals and per capita range | Trade press summary | NAADGS report PDF |
| Count of legal states (39 plus DC) and the online versus retail split | Two trackers that disagree on classification | Built from our own per-state records; the site will publish its classification rule rather than adopt a tracker's count |

## Things this design deliberately does not do

- It does not attempt causal claims. Outcome series are shown with
  legalization dates marked and with the limitations text on the same
  page. Causal estimates appear only in the research library, attributed
  to their authors, with the unit of effect stated.
- It does not store any derived number. If a staffer recomputes a per
  capita figure from the CSV and the population table, they get the same
  number the page shows.
- It does not use trade press as a citable source for any figure.
- It does not aggregate across market segments without a label.
