// Static CSV of the headline status table, generated at build from the same
// records as the map. One row per jurisdiction. Provenance columns carry the
// retail and online legal_status sources so the file is citable on its own.
import type { APIRoute } from 'astro';
import { profiles, headlineStatus, scopeQualifiers, earliestLaunch, source, commitHash, BUILD_DATE } from '../../lib/data';

function q(v: unknown): string {
  const s = v == null ? '' : String(v);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

export const GET: APIRoute = () => {
  const cols = ['fips', 'abbr', 'name', 'headline_status', 'qualifiers', 'first_launch', 'retail_status', 'retail_scope', 'retail_launched_on', 'retail_source_publisher', 'retail_source_url', 'retail_retrieved_at', 'retail_record_status', 'online_status', 'online_scope', 'online_launched_on', 'online_source_publisher', 'online_source_url', 'online_retrieved_at', 'online_record_status', 'profile_completeness'];
  const lines = [`# Wagering Policy Data Center, state headline status. Built ${BUILD_DATE} from commit ${commitHash()}. License CC BY 4.0. Regulated sportsbooks only; prediction markets are tracked separately.`, cols.join(',')];
  for (const p of profiles()) {
    const r = p.legal_status.find((x) => x.channel === 'retail');
    const o = p.legal_status.find((x) => x.channel === 'online');
    const ch = (x: typeof r) => x ? [x.status, x.scope, x.launched_on ?? '', source(x.provenance.source_id).publisher, x.provenance.source_url, x.provenance.retrieved_at, x.provenance.status] : ['', '', '', '', '', '', ''];
    lines.push([p.fips, p.abbr, p.name, headlineStatus(p), scopeQualifiers(p).join('; '), earliestLaunch(p) ?? '', ...ch(r), ...ch(o), p.profile_completeness ?? ''].map(q).join(','));
  }
  return new Response(lines.join('\n') + '\n', { headers: { 'Content-Type': 'text/csv; charset=utf-8' } });
};
