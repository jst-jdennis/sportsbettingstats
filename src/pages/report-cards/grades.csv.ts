// Static CSV of the state report card grades, generated at build from the committed grades file,
// which scripts/grade.py --check keeps identical to a fresh computation from the rubric and the data.
import type { APIRoute } from 'astro';
import { grades, commitHash, BUILD_DATE } from '../../lib/data';

function q(v: unknown): string {
  const s = v == null ? '' : String(v);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

export const GET: APIRoute = () => {
  const g = grades();
  const criteria = g ? g.states[0].criteria.map((c) => c.criterion_id) : [];
  const all = g ? Array.from(new Set(g.states.flatMap((s) => s.criteria.map((c) => c.criterion_id)))) : [];
  const cols = ['fips', 'abbr', 'name', 'market', 'status', 'review', 'grade', 'pct', 'points', 'available', 'inputs_pending_review', 'missing_criteria', ...all.map((c) => `points_${c}`)];
  const lines = [`# Wagering Policy Data Center, state report card grades, rubric ${g?.rubric_version ?? 'none'} (${g?.rubric_status ?? ''}). Built ${BUILD_DATE} from commit ${commitHash()}; data fingerprint ${g?.data_fingerprint ?? ''}. License CC BY 4.0. Grades measure adopted consumer protection policy, not outcomes; incomplete means inputs are not yet entered, provisional means inputs are pending review.`, cols.join(',')];
  void criteria;
  for (const s of g?.states ?? []) {
    const by = Object.fromEntries(s.criteria.map((c) => [c.criterion_id, c.status === 'scored' ? c.points : '']));
    lines.push([s.fips, s.abbr, s.name, s.market, s.status, s.review ?? '', s.grade ?? '', s.pct ?? '', s.points, s.available, s.inputs_pending_review, s.missing_criteria.join('; '), ...all.map((c) => (c in by ? by[c] : 'n/a'))].map(q).join(','));
  }
  return new Response(lines.join('\n') + '\n', { headers: { 'Content-Type': 'text/csv; charset=utf-8' } });
};
