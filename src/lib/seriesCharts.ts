// Build-time charts for the outcome time series. Each function returns the
// SVG, the caption and a DataTable (the rows the Chart component shows and the
// CSV endpoint serves), so the outcomes page and the state pages render the
// same thing from one place. Series are descriptive: legalization dates are
// marked, never attributed.
import { handleRevenue, bankruptcy, helpline, population, legalizationMarkers, fmtDate, label, source, type StateProfile } from './data';
import { lineChart, compact, esc } from './charts';
import { seriesProv, D, USD, N, R, type DataTable, type Cell } from './tables';

export const MIN_POINTS = 3;

// The CSV loaders parse the file on every call; read each once per build and filter here.
let _hr: ReturnType<typeof handleRevenue> | null = null, _bk: ReturnType<typeof bankruptcy> | null = null, _hl: ReturnType<typeof helpline> | null = null;
export const hrFor = (fips: string) => (_hr ??= handleRevenue()).filter((r) => r.fips === fips);
export const bkFor = (fips: string) => (_bk ??= bankruptcy()).filter((r) => r.fips === fips);
export const hlFor = (fips: string) => (_hl ??= helpline()).filter((r) => r.fips === fips);
// population() parses its CSV on every call and per100k calls it once per point; index it once here instead.
let _pop: Map<string, ReturnType<typeof population>> | null = null;
function populationFor(fips: string, year: number) {
  if (!_pop) { _pop = new Map(); for (const r of population()) { if (r.status === 'superseded') continue; if (!_pop.has(r.fips)) _pop.set(r.fips, []); _pop.get(r.fips)!.push(r); } }
  const rows = _pop.get(fips);
  if (!rows?.length) return null;
  return [...rows].sort((a, b) => Math.abs(Number(a.year) - year) - Math.abs(Number(b.year) - year) || Number(b.vintage) - Number(a.vintage))[0];
}
/** Same result as data.ts per100k, computed against the cached population index. */
export function per100k(count: number, fips: string, year: number) {
  const pop = populationFor(fips, year);
  return pop ? { value: (count / Number(pop.population)) * 100000, pop } : null;
}

/** Decimal year for a date, so months and quarters share one axis. */
export function dateX(d: string): number { const [y, m, day] = d.split('-').map(Number); return y + ((m ?? 1) - 1) / 12 + ((day ?? 1) - 1) / 365; }
const yearTicks = (xs: number[]) => { const a = Math.floor(Math.min(...xs)), b = Math.ceil(Math.max(...xs)); const step = b - a > 12 ? 2 : 1; const out = []; for (let y = a; y <= b; y += step) out.push(y); return out; };
const usd = (v: number) => `${v < 0 ? '-' : ''}$${compact(Math.abs(v))}`;
export const monthName = (d: string) => fmtDate(d.slice(0, 7) + '-01').replace(/ 1, /, ' ');
const provLine = (r: { source_id: string; retrieved_at: string; status: string }) => `${source(r.source_id).publisher}, retrieved ${fmtDate(r.retrieved_at)}, ${label(r.status)}`;
/** A month cell: "June 2018" on the page, the ISO period start in the CSV. */
export const M = (d: string): Cell => ({ text: monthName(d), value: d });

export interface SeriesChart { svg: string; legend: { cls: string; name: string }[]; table: DataTable; caption: string; title: string; n: number }
/** Where the table lives: the page path and the id the CSV is served under. */
export interface TableAt { page: string; id: string }

/** Monthly gross sports wagering revenue by channel. Handle is plotted only when the regulator publishes it. */
export function revenueChart(p: StateProfile, at: TableAt): SeriesChart | null {
  const rows = hrFor(p.fips).filter((r) => r.market_segment === 'regulated_sportsbook' && r.gross_revenue_usd !== '');
  const channels = (['retail', 'online'] as const).filter((c) => rows.some((r) => r.channel === c));
  const series = channels.map((c, i) => ({ name: label(c).replace(/^./, (ch) => ch.toUpperCase()), cls: i === 0 ? 's1' : 's2', points: rows.filter((r) => r.channel === c).map((r) => ({ x: dateX(r.period_start), y: Number(r.gross_revenue_usd), title: `${label(c)}, ${monthName(r.period_start)}: gross revenue ${usd(Number(r.gross_revenue_usd))}${r.state_tax_usd ? `, tax ${usd(Number(r.state_tax_usd))}` : ''}${r.is_revised === 'true' ? ' (revised)' : ''}` })) }));
  const n = Math.max(0, ...series.map((s) => s.points.length));
  if (n < MIN_POINTS) return null;
  const markers = legalizationMarkers(p).map((mk) => ({ x: dateX(mk.date), label: mk.label }));
  const xs = series.flatMap((s) => s.points.map((pt) => pt.x));
  const hasHandle = rows.some((r) => r.handle_usd !== '');
  const first = rows[0], last = rows[rows.length - 1];
  const svg = lineChart({ id: `rev-${p.abbr.toLowerCase()}`, title: `${p.name}: monthly gross sports wagering revenue by channel`, desc: 'Line chart of monthly gross revenue for each channel, with vertical lines at the first legal wager in each channel. The same values are in the table below.', series, markers, xTicks: yearTicks(xs), xFmt: String, yFmt: usd, dotR: 2.5, gapX: 0.2, hollow: rows.every((r) => r.status !== 'verified'), height: 320 });
  const all = rows.filter((r) => r.channel === 'all');
  return {
    svg, n, title: `${p.name}: monthly gross revenue`, legend: series.map((s) => ({ cls: s.cls, name: `${s.name} gross revenue` })),
    table: revenueTable(p, at, rows),
    caption: `${monthName(first.period_start)} to ${monthName(last.period_start)}, ${all.length || n} months. Gross revenue before promotional deductions, as the regulator defines it: ${rows[0].revenue_definition} ${hasHandle ? '' : 'Handle (the amount wagered) is not published in any primary document from this regulator, so it is not shown and no hold percentage is computed. '}Not seasonally adjusted; months follow the sports calendar. Source: ${provLine(last)}.`,
  };
}

/** Monthly revenue rows as a table, in dollars as reported for the period. */
export function revenueTable(p: StateProfile, at: TableAt, rows = hrFor(p.fips)): DataTable {
  return {
    ...at, title: `${p.name}: monthly sports wagering handle, revenue and tax by channel`,
    head: ['Month', 'Channel', 'Handle', 'Gross revenue', 'Taxable revenue', 'Promotional deductions', 'State tax', 'Revised'],
    rows: rows.map((r) => [M(r.period_start), label(r.channel), USD(r.handle_usd, 'not published'), USD(r.gross_revenue_usd, 'not reported'), USD(r.adjusted_revenue_usd, 'not reported'), USD(r.promo_deductions_usd, 'not reported'), USD(r.state_tax_usd, 'not reported'), r.is_revised === 'true' ? 'yes' : 'no']),
    prov: rows.map(seriesProv), num: [2, 3, 4, 5, 6],
    note: rows.length ? `Dollars as reported by the regulator for the period, not seasonally adjusted. Revenue definition: ${rows[0].revenue_definition}` : null,
  };
}

/** Bankruptcy rows as a table, with filings per 100,000 computed at build time from the population table. */
export function bankruptcyTable(p: StateProfile, at: TableAt, rows = bkFor(p.fips).filter((r) => r.chapter === 'all_nonbusiness')): DataTable {
  const pts = rows.map((r) => ({ r, pk: per100k(Number(r.filings), r.fips, Number(r.period_end.slice(0, 4))) }));
  return {
    ...at, title: `${p.name}: nonbusiness bankruptcy filings and filings per 100,000 residents`,
    head: ['Period start', 'Period end', 'Measure', 'Filings', 'Per 100,000', 'Population', 'Population year'],
    rows: pts.map(({ r, pk }) => [D(r.period_start), D(r.period_end), label(r.measure), N(r.filings), R(pk?.value, 1, 'no population row'), N(pk?.pop?.population), pk?.pop?.year ?? '']),
    prov: rows.map(seriesProv), num: [3, 4, 5],
    note: 'Nonbusiness filings from Table F-2 of the Administrative Office of the US Courts. Per 100,000 uses the Census estimate for the year each period ends and is computed at build time, never stored. Quarter and twelve-month rows overlap; filter on Measure before summing.',
  };
}

/** Quarterly nonbusiness bankruptcy filings per 100,000 residents. */
export function bankruptcyChart(p: StateProfile, at: TableAt): SeriesChart | null {
  const rows = bkFor(p.fips).filter((r) => r.measure === 'quarter' && r.chapter === 'all_nonbusiness');
  const pts = rows.map((r) => ({ r, pk: per100k(Number(r.filings), r.fips, Number(r.period_end.slice(0, 4))) })).filter((x) => x.pk);
  if (pts.length < MIN_POINTS) return null;
  const series = [{ name: 'Filings per 100,000', cls: 's1', points: pts.map(({ r, pk }) => ({ x: dateX(r.period_start), y: Math.round(pk!.value * 10) / 10, title: `Quarter ${fmtDate(r.period_start)} to ${fmtDate(r.period_end)}: ${Number(r.filings).toLocaleString()} filings, ${pk!.value.toFixed(1)} per 100,000 (population ${Number(pk!.pop!.population).toLocaleString()}, ${pk!.pop!.year})` })) }];
  const markers = legalizationMarkers(p).map((mk) => ({ x: dateX(mk.date), label: mk.label }));
  const xs = series[0].points.map((pt) => pt.x);
  const inRange = markers.filter((mk) => mk.x >= Math.min(...xs) && mk.x <= Math.max(...xs));
  const gaps = pts.slice(1).some(({ r }, i) => dateX(r.period_start) - dateX(pts[i].r.period_start) > 0.3);
  const svg = lineChart({ id: `bk-${p.abbr.toLowerCase()}`, title: `${p.name}: nonbusiness bankruptcy filings per 100,000 residents, by quarter`, desc: 'Line chart of quarterly filings per 100,000 residents, with vertical lines at the first legal wager in each channel where those dates fall within the series.', series, markers, xTicks: yearTicks(xs), xFmt: String, yFmt: (v) => String(v), gapX: 0.3, hollow: rows.every((r) => r.status !== 'verified'), height: 280 });
  const last = pts[pts.length - 1].r;
  const table = bankruptcyTable(p, at, pts.map((x) => x.r));
  table.title = `${p.name}: quarterly nonbusiness bankruptcy filings per 100,000 residents, as charted`;
  return {
    svg, n: pts.length, title: `${p.name}: quarterly bankruptcy filings per 100,000`, legend: [], table,
    caption: `${pts.length} quarters on file${gaps ? ', with the line broken where quarters have not yet been ingested' : ''}. ${inRange.length ? 'Vertical lines mark the first legal wager in each channel. A change after a line is shown, not attributed: filings respond to exemption law, income, debt, medical costs and court practice, and the series has breaks at the 2020 to 2021 trough.' : `${p.name}'s legalization dates fall before the first quarter on file, so no marker is shown; the back series to 2018 is being ingested.`} Per 100,000 uses the Census estimate for the year each quarter ends and is computed at build time, never stored. Source: ${provLine(last)}.`,
  };
}

/** Helpline rows as a table; `withState` adds a leading State column for a table that spans states. */
export function helplineTable(rows: ReturnType<typeof helpline>, at: TableAt, title: string, stateName?: (fips: string) => string): DataTable {
  return {
    ...at, title,
    head: [...(stateName ? ['State'] : []), 'Period start', 'Period end', 'Type', 'Contacts', 'Operator', 'Counting rule', 'Notes'],
    rows: rows.map((r) => [...(stateName ? [stateName(r.fips)] : []), D(r.period_start), D(r.period_end), label(r.contact_type), N(r.contacts), r.operator, r.counting_rule, r.notes ?? '']),
    prov: rows.map(seriesProv),
    note: 'Helpline volume rises when the number is advertised more, so it measures help-seeking and awareness, not prevalence. Each row carries the operator\'s own counting rule; rows with different rules are not strictly comparable.',
  };
}

/** Helpline contacts by period, for one state. Null when fewer than MIN_POINTS periods are on file; the table still renders. */
export function helplineChart(p: StateProfile, at: TableAt): SeriesChart | null {
  const rows = hlFor(p.fips);
  if (rows.length < MIN_POINTS) return null;
  const types = [...new Set(rows.map((r) => r.contact_type))];
  const series = types.map((t, i) => ({ name: `${label(t)}s`, cls: ['s1', 's2', 's3'][i] ?? 's0', points: rows.filter((r) => r.contact_type === t).map((r) => ({ x: dateX(r.period_start), y: Number(r.contacts), title: `${fmtDate(r.period_start)} to ${fmtDate(r.period_end)}: ${Number(r.contacts).toLocaleString()} ${label(t)}s, ${r.operator}` })) }));
  const markers = legalizationMarkers(p).map((mk) => ({ x: dateX(mk.date), label: mk.label }));
  const xs = series.flatMap((s) => s.points.map((pt) => pt.x));
  const gaps = rows.slice(1).some((r, i) => dateX(r.period_start) - dateX(rows[i].period_start) > 1.1);
  const operators = [...new Set(rows.map((r) => r.operator))];
  const rules = [...new Set(rows.map((r) => r.counting_rule))];
  const svg = lineChart({ id: `hl-${p.abbr.toLowerCase()}`, title: `${p.name}: problem gambling helpline contacts by period`, desc: 'Line chart of helpline contacts per reporting period, with vertical lines at the first legal wager in each channel.', series, markers, xTicks: yearTicks(xs), xFmt: String, yFmt: compact, gapX: 1.1, hollow: rows.every((r) => r.status !== 'verified'), height: 280 });
  return {
    svg, n: rows.length, title: `${p.name}: helpline contacts`, legend: series.map((s) => ({ cls: s.cls, name: s.name })),
    table: helplineTable(rows, at, `${p.name}: problem gambling helpline contacts by period`),
    caption: `${rows.length} periods${gaps ? ', with the line broken where reports have not been found' : ''}. Operator: ${operators.join('; ')}. ${rules.length > 1 ? `The counting rule differs between the source documents (${rules.length} rules across the periods), so periods from different documents are not strictly comparable; each row states its rule and any note. ` : ''}Helpline volume rises when the number is advertised more, including when operators are required to print it, so it measures help-seeking and awareness, not prevalence. Source: ${provLine(rows[rows.length - 1])}.`,
  };
}
export { esc };
