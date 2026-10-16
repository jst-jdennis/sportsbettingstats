// Single place for the site identity. Changing the name or domain happens here
// and in astro.config.mjs (site/base), nowhere else.
export const SITE = {
  name: 'Wagering Policy Data Center',
  shortName: 'WPDC',
  tagline: 'State-by-state data on legalized sports betting and prediction markets',
  description:
    'An open, nonpartisan reference on the legal status, consumer protections and measured outcomes of sports wagering and prediction markets in every US state. Every figure links to its primary source.',
  repoUrl: 'https://github.com/jst-jdennis/sportsbettingstats',
  dataLicense: { name: 'CC BY 4.0', url: 'https://creativecommons.org/licenses/by/4.0/' },
  codeLicense: { name: 'AGPL-3.0', url: 'https://www.gnu.org/licenses/agpl-3.0.html' },
  contactIssuesUrl: 'https://github.com/jst-jdennis/sportsbettingstats/issues/new/choose',
  phase: 'Draft',
} as const;
