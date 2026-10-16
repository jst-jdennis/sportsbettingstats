// Build-time chart rendering to static SVG. No client JavaScript: every chart
// is an <svg> string with a <title> on each mark for native hover text, and
// the Chart component prints the same numbers in a table under the figure.
//
// Colors are never hard-coded here. Marks carry classes (s1, s2, s3 for the
// three categorical slots; grid, base, ax for chrome) that global.css maps to
// CSS custom properties, so light and dark mode come from the one stylesheet.

export function esc(s: string | number | null | undefined): string {
  return String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

/** Greedy word wrap to at most `lines` lines of about `chars` characters; the last line is cut with an ellipsis if text remains. */
export function wrap(text: string, chars: number, lines = 2): string[] {
  const words = text.split(/\s+/);
  const out: string[] = [];
  let cur = '';
  for (const w of words) {
    if ((cur + ' ' + w).trim().length > chars && cur) { out.push(cur); cur = w; if (out.length === lines) break; }
    else cur = (cur + ' ' + w).trim();
  }
  if (out.length < lines && cur) out.push(cur);
  const used = out.join(' ').length;
  if (used < text.length) out[out.length - 1] = out[out.length - 1].replace(/[\s,;:]*$/, '') + '...';
  return out;
}
const CHAR_W = 6.2; // approximate rendered width of one character at 11px, used only for collision checks
const M = { top: 12, right: 16, bottom: 28, left: 40 };

function svgOpen(w: number, h: number, title: string, desc: string, id: string): string {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${w} ${h}" role="img" aria-labelledby="${id}-t ${id}-d" class="chart-svg" style="aspect-ratio:${w}/${h}"><title id="${id}-t">${esc(title)}</title><desc id="${id}-d">${esc(desc)}</desc>`;
}

/** Nice tick values for a linear axis. */
export function ticks(min: number, max: number, count = 5): number[] {
  if (max === min) return [min];
  const span = max - min;
  const raw = span / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const norm = raw / mag;
  const step = (norm >= 5 ? 10 : norm >= 2 ? 5 : norm >= 1 ? 2 : 1) * mag;
  const out: number[] = [];
  for (let v = Math.ceil(min / step) * step; v <= max + 1e-9; v += step) out.push(Number(v.toFixed(10)));
  return out;
}

export function compact(n: number): string {
  const a = Math.abs(n);
  if (a >= 1e9) return `${(n / 1e9).toFixed(1).replace(/\.0$/, '')}B`;
  if (a >= 1e6) return `${(n / 1e6).toFixed(1).replace(/\.0$/, '')}M`;
  if (a >= 1e3) return `${(n / 1e3).toFixed(1).replace(/\.0$/, '')}K`;
  return String(n);
}

/** A rect with the data end rounded and the baseline end square (horizontal bar growing to the right). */
function barRight(x: number, y: number, w: number, h: number, r = 4): string {
  if (w <= 0) return '';
  const rr = Math.min(r, w, h / 2);
  return `M${x},${y} h${w - rr} a${rr},${rr} 0 0 1 ${rr},${rr} v${h - 2 * rr} a${rr},${rr} 0 0 1 -${rr},${rr} h-${w - rr} z`;
}

// ---------------------------------------------------------------- line chart

export interface LinePoint { x: number; y: number; title?: string }
export interface LineSeries { name: string; cls: string; points: LinePoint[] }
export interface LineChartOpts {
  id: string; title: string; desc: string; series: LineSeries[];
  xFmt?: (x: number) => string; yFmt?: (y: number) => string; width?: number; height?: number; yMax?: number; xTicks?: number[]; step?: boolean;
  /** Vertical reference lines, for example legalization dates, in x units. Labels stack at the top. */
  markers?: { x: number; label: string }[];
  /** Marker radius; use 3 for dense monthly series. Default 4. */
  dotR?: number;
  /** Draw markers hollow (pending review convention). */
  hollow?: boolean;
  /** Break the line where consecutive points are further apart than this many x units (a gap in the series). */
  gapX?: number;
}

/** Multi-series line (or step) chart with end markers and selective end labels. */
export function lineChart(o: LineChartOpts): string {
  const W = o.width ?? 720, H = o.height ?? 300;
  const m = { ...M, right: 120 };
  const pw = W - m.left - m.right, ph = H - m.top - m.bottom;
  const xs = o.series.flatMap((s) => s.points.map((p) => p.x)), ys = o.series.flatMap((s) => s.points.map((p) => p.y));
  const xT = o.xTicks ?? ticks(Math.min(...xs), Math.max(...xs), 6);
  // The plot spans the data and the outer ticks, so the axis ends on a tick and end labels have room.
  const x0 = Math.min(...xs, xT[0]), x1 = Math.max(...xs, xT[xT.length - 1]);
  const y1 = o.yMax ?? Math.max(...ys) * 1.08; // headroom so the peak never sits on the frame
  const yMin = Math.min(0, ...ys);
  const yT = ticks(yMin, y1, 4); const yTop = yT[yT.length - 1] >= y1 ? yT[yT.length - 1] : y1; const yBot = Math.min(yMin, yT[0]);
  const sx = (x: number) => m.left + (x1 === x0 ? 0 : ((x - x0) / (x1 - x0)) * pw);
  const sy = (y: number) => m.top + ph - ((y - yBot) / (yTop - yBot)) * ph;
  const r = o.dotR ?? 4;
  const xf = o.xFmt ?? String, yf = o.yFmt ?? compact;
  let out = svgOpen(W, H, o.title, o.desc, o.id);
  for (const t of yT) out += `<line class="grid" x1="${m.left}" x2="${W - m.right}" y1="${sy(t).toFixed(1)}" y2="${sy(t).toFixed(1)}"/><text class="ax" x="${m.left - 6}" y="${(sy(t) + 4).toFixed(1)}" text-anchor="end">${esc(yf(t))}</text>`;
  for (const t of xT) out += `<text class="ax" x="${sx(t).toFixed(1)}" y="${H - 8}" text-anchor="middle">${esc(xf(t))}</text>`;
  out += `<line class="base" x1="${m.left}" x2="${W - m.right}" y1="${sy(0)}" y2="${sy(0)}"/>`;
  // Markers on the same date (within about two weeks) share one line and one label. Labels flip to the left near the right edge.
  const merged: { x: number; label: string }[] = [];
  for (const mk of (o.markers ?? []).filter((mk) => mk.x >= x0 && mk.x <= x1).sort((a, b) => a.x - b.x)) {
    const last = merged[merged.length - 1];
    if (last && mk.x - last.x < 0.05) last.label = last.label.replace(/^First (\w+) wager$/, (_, c) => `First ${c} and ${mk.label.replace(/^First (\w+) wager$/, '$1')} wager`) || `${last.label}; ${mk.label}`;
    else merged.push({ ...mk });
  }
  // Labels sit at the top unless the data near the marker is high, in which case they sit just above the baseline.
  const allPts = o.series.flatMap((s) => s.points);
  const highNear = merged.some((mk) => allPts.some((p) => Math.abs(p.x - mk.x) < (x1 - x0) * 0.12 && p.y > yBot + (yTop - yBot) * 0.7));
  merged.forEach((mk, i) => {
    const X = sx(mk.x), flip = X > W - m.right - mk.label.length * CHAR_W - 8;
    const Y = highNear ? H - m.bottom - 6 - (merged.length - 1 - i) * 12 : m.top + 10 + i * 12;
    out += `<line class="marker" x1="${X.toFixed(1)}" x2="${X.toFixed(1)}" y1="${m.top}" y2="${H - m.bottom}"/><text class="ax" x="${(flip ? X - 4 : X + 4).toFixed(1)}" y="${Y}"${flip ? ' text-anchor="end"' : ''}>${esc(mk.label)}</text>`;
  });
  const ends: { y: number; label: string; cls: string }[] = [];
  for (const s of o.series) {
    const pts = [...s.points].sort((a, b) => a.x - b.x);
    let d = '';
    pts.forEach((p, i) => {
      const X = sx(p.x).toFixed(1), Y = sy(p.y).toFixed(1);
      const gap = i > 0 && o.gapX != null && p.x - pts[i - 1].x > o.gapX;
      if (i === 0 || gap) d += `M${X},${Y}`;
      else if (o.step) d += `H${X}V${Y}`;
      else d += `L${X},${Y}`;
    });
    out += `<path class="line ${s.cls}" d="${d}"/>`;
    for (const p of pts) out += `<circle class="dot ${s.cls}${o.hollow ? ' hollow' : ''}" cx="${sx(p.x).toFixed(1)}" cy="${sy(p.y).toFixed(1)}" r="${r}"><title>${esc(p.title ?? `${s.name}, ${xf(p.x)}: ${yf(p.y)}`)}</title></circle>`;
    const last = pts[pts.length - 1];
    ends.push({ y: sy(last.y), label: `${s.name} (${yf(last.y)})`, cls: s.cls });
  }
  // End labels: nudge apart if they collide, keeping a short leader.
  ends.sort((a, b) => a.y - b.y);
  for (let i = 1; i < ends.length; i++) if (ends[i].y - ends[i - 1].y < 14) ends[i].y = ends[i - 1].y + 14;
  for (const e of ends) out += `<text class="lbl" x="${W - m.right + 8}" y="${(e.y + 4).toFixed(1)}">${esc(e.label)}</text>`;
  return out + '</svg>';
}

// ------------------------------------------------------- horizontal bar chart

export interface BarSegment { value: number; cls: string; name: string; title?: string }
export interface BarRow { label: string; sub?: string; segments: BarSegment[]; href?: string }
export interface BarChartOpts {
  id: string; title: string; desc: string; rows: BarRow[]; max?: number; width?: number; rowHeight?: number; labelWidth?: number;
  fmt?: (v: number) => string; valueLabel?: boolean; markers?: { value: number; label: string }[];
}

/** Horizontal stacked bars. Bars are at most 20px thick, rounded at the data end, with a 2px surface gap between segments. */
export function barChartH(o: BarChartOpts): string {
  const rh = o.rowHeight ?? 26, lw = o.labelWidth ?? 170, W = o.width ?? 720;
  const m = { top: 8, right: 56, bottom: 26, left: lw };
  const H = m.top + o.rows.length * rh + m.bottom;
  const pw = W - m.left - m.right;
  const totals = o.rows.map((r) => r.segments.reduce((a, s) => a + s.value, 0));
  const max = o.max ?? Math.max(1, ...totals);
  const xT = ticks(0, max, 4); const xMax = Math.max(max, xT[xT.length - 1]);
  const sx = (v: number) => m.left + (v / xMax) * pw;
  const fmt = o.fmt ?? compact;
  const bh = Math.min(20, rh - 6);
  let out = svgOpen(W, H, o.title, o.desc, o.id);
  for (const t of xT) out += `<line class="grid" x1="${sx(t).toFixed(1)}" x2="${sx(t).toFixed(1)}" y1="${m.top}" y2="${H - m.bottom}"/><text class="ax" x="${sx(t).toFixed(1)}" y="${H - 8}" text-anchor="middle">${esc(fmt(t))}</text>`;
  out += `<line class="base" x1="${m.left}" x2="${m.left}" y1="${m.top}" y2="${H - m.bottom}"/>`;
  o.rows.forEach((r, i) => {
    const y = m.top + i * rh + (rh - bh) / 2;
    const lab = `<text class="lbl" x="${m.left - 8}" y="${(y + bh / 2 + 4).toFixed(1)}" text-anchor="end">${esc(r.label)}</text>`;
    out += r.href ? `<a href="${esc(r.href)}">${lab}</a>` : lab;
    if (r.sub) out += `<text class="ax" x="${m.left - 8}" y="${(y + bh / 2 + 15).toFixed(1)}" text-anchor="end">${esc(r.sub)}</text>`;
    let acc = 0;
    const segs = r.segments.filter((s) => s.value > 0);
    segs.forEach((s, j) => {
      const x = sx(acc), w = sx(acc + s.value) - sx(acc);
      const gap = j < segs.length - 1 ? 2 : 0;
      const t = `<title>${esc(s.title ?? `${r.label}, ${s.name}: ${fmt(s.value)}`)}</title>`;
      out += j === segs.length - 1
        ? `<path class="${s.cls}" d="${barRight(x, y, Math.max(0, w - gap), bh)}">${t}</path>`
        : `<rect class="${s.cls}" x="${x.toFixed(1)}" y="${y}" width="${Math.max(0, w - gap).toFixed(1)}" height="${bh}">${t}</rect>`;
      acc += s.value;
    });
    if (o.valueLabel !== false) out += `<text class="val" x="${(sx(acc) + 6).toFixed(1)}" y="${(y + bh / 2 + 4).toFixed(1)}">${esc(fmt(acc))}</text>`;
  });
  for (const mk of o.markers ?? []) out += `<line class="marker" x1="${sx(mk.value).toFixed(1)}" x2="${sx(mk.value).toFixed(1)}" y1="${m.top - 4}" y2="${H - m.bottom}"/><text class="ax" x="${(sx(mk.value) + 4).toFixed(1)}" y="${m.top + 6}">${esc(mk.label)}</text>`;
  return out + '</svg>';
}

// ---------------------------------------------------------------- dot plot

export interface DotRow { label: string | string[]; sub?: string; value: number; low?: number | null; high?: number | null; cls: string; title: string; href?: string; hollow?: boolean }
export interface DotPlotOpts { id: string; title: string; desc: string; rows: DotRow[]; fmt?: (v: number) => string; width?: number; rowHeight?: number; labelWidth?: number; zeroLabel?: string; groups?: { label: string; at: number }[] }

/** Dot plot of signed estimates around zero, with an optional range bar per row. */
export function dotPlot(o: DotPlotOpts): string {
  const rh = o.rowHeight ?? 34, lw = o.labelWidth ?? 250, W = o.width ?? 760;
  const groupRows = (o.groups ?? []).length;
  const m = { top: 10, right: 60, bottom: 26, left: lw };
  const H = m.top + (o.rows.length + groupRows) * rh + m.bottom;
  const pw = W - m.left - m.right;
  const vals = o.rows.flatMap((r) => [r.value, r.low ?? r.value, r.high ?? r.value]);
  const lo = Math.min(0, ...vals), hi = Math.max(0, ...vals);
  const xT = ticks(lo, hi, 5);
  const xMin = Math.min(lo, xT[0]), xMax = Math.max(hi, xT[xT.length - 1]);
  const sx = (v: number) => m.left + ((v - xMin) / (xMax - xMin)) * pw;
  const fmt = o.fmt ?? String;
  let out = svgOpen(W, H, o.title, o.desc, o.id);
  for (const t of xT) out += `<line class="grid" x1="${sx(t).toFixed(1)}" x2="${sx(t).toFixed(1)}" y1="${m.top}" y2="${H - m.bottom}"/><text class="ax" x="${sx(t).toFixed(1)}" y="${H - 8}" text-anchor="middle">${esc(fmt(t))}</text>`;
  out += `<line class="base" x1="${sx(0).toFixed(1)}" x2="${sx(0).toFixed(1)}" y1="${m.top}" y2="${H - m.bottom}"/>`;
  if (o.zeroLabel) out += `<text class="ax" x="${(sx(0) + 4).toFixed(1)}" y="${m.top + 2}">${esc(o.zeroLabel)}</text>`;
  // Interleave group headers at the row indexes given.
  let row = 0, gi = 0;
  const groups = [...(o.groups ?? [])].sort((a, b) => a.at - b.at);
  o.rows.forEach((r, i) => {
    while (gi < groups.length && groups[gi].at === i) { out += `<text class="grp" x="${m.left - 8}" y="${m.top + row * rh + rh / 2 + 4}" text-anchor="end">${esc(groups[gi].label)}</text>`; row++; gi++; }
    const cy = m.top + row * rh + rh / 2;
    const lines = Array.isArray(r.label) ? r.label : [r.label];
    const n = lines.length + (r.sub ? 1 : 0);
    const y0 = cy - ((n - 1) * 13) / 2 + 4;
    const lab = `<text class="lbl" x="${m.left - 8}" y="${y0.toFixed(1)}" text-anchor="end">${lines.map((l, k) => `<tspan x="${m.left - 8}" dy="${k ? 13 : 0}">${esc(l)}</tspan>`).join('')}</text>`;
    out += r.href ? `<a href="${esc(r.href)}">${lab}</a>` : lab;
    if (r.sub) out += `<text class="ax" x="${m.left - 8}" y="${(y0 + lines.length * 13).toFixed(1)}" text-anchor="end">${esc(r.sub)}</text>`;
    if (r.low != null && r.high != null) out += `<line class="range ${r.cls}" x1="${sx(r.low).toFixed(1)}" x2="${sx(r.high).toFixed(1)}" y1="${cy}" y2="${cy}"/>`;
    out += `<circle class="dot ${r.cls}${r.hollow ? ' hollow' : ''}" cx="${sx(r.value).toFixed(1)}" cy="${cy}" r="6"><title>${esc(r.title)}</title></circle>`;
    out += `<text class="val" x="${(sx(Math.max(r.value, r.high ?? r.value)) + 10).toFixed(1)}" y="${cy + 4}">${esc(fmt(r.value))}</text>`;
    row++;
  });
  return out + '</svg>';
}

// ---------------------------------------------------------------- timeline

export interface TimelineEvent { date: string; cls: string; title: string; label?: string; href?: string }
export interface TimelineRow { label: string; events: TimelineEvent[]; href?: string }
export interface TimelineOpts { id: string; title: string; desc: string; rows: TimelineRow[]; start?: string; end?: string; width?: number; rowHeight?: number; labelWidth?: number }

function dateNum(d: string): number {
  const [y, m, day] = d.split('-').map(Number);
  return y + ((m ?? 1) - 1) / 12 + ((day ?? 1) - 1) / 365;
}

/** Rows of dated events on a shared year axis. */
export function timeline(o: TimelineOpts): string {
  const rh = o.rowHeight ?? 30, lw = o.labelWidth ?? 160, W = o.width ?? 720;
  const m = { top: 10, right: 20, bottom: 26, left: lw };
  const H = m.top + o.rows.length * rh + m.bottom;
  const pw = W - m.left - m.right;
  const all = o.rows.flatMap((r) => r.events.map((e) => dateNum(e.date)));
  const x0 = o.start ? dateNum(o.start) : Math.floor(Math.min(...all));
  const x1 = o.end ? dateNum(o.end) : Math.ceil(Math.max(...all) + 0.5);
  const sx = (v: number) => m.left + ((v - x0) / (x1 - x0)) * pw;
  let out = svgOpen(W, H, o.title, o.desc, o.id);
  const yearStep = x1 - x0 > 14 ? 2 : 1;
  for (let y = Math.ceil(x0); y <= x1; y += yearStep) out += `<line class="grid" x1="${sx(y).toFixed(1)}" x2="${sx(y).toFixed(1)}" y1="${m.top}" y2="${H - m.bottom}"/><text class="ax" x="${sx(y).toFixed(1)}" y="${H - 8}" text-anchor="middle">${y}</text>`;
  o.rows.forEach((r, i) => {
    const cy = m.top + i * rh + rh / 2;
    out += `<line class="track" x1="${m.left}" x2="${W - m.right}" y1="${cy}" y2="${cy}"/>`;
    const lab = `<text class="lbl" x="${m.left - 8}" y="${cy + 4}" text-anchor="end">${esc(r.label)}</text>`;
    out += r.href ? `<a href="${esc(r.href)}">${lab}</a>` : lab;
    const evs = [...r.events].sort((a, b) => dateNum(a.date) - dateNum(b.date));
    let lastLabelX = -Infinity;
    for (const e of evs) {
      const cx = sx(dateNum(e.date));
      const dot = `<circle class="dot ${e.cls}" cx="${cx.toFixed(1)}" cy="${cy}" r="6"><title>${esc(e.title)}</title></circle>`;
      out += e.href ? `<a href="${esc(e.href)}">${dot}</a>` : dot;
      if (e.label && cx > lastLabelX) {
        const lw = e.label.length * CHAR_W;
        const flip = cx + 9 + lw > W - m.right; // keep the label inside the plot: anchor it to the left of the dot near the right edge
        out += `<text class="ax" x="${(flip ? cx - 9 : cx + 9).toFixed(1)}" y="${cy - 8}"${flip ? ' text-anchor="end"' : ''}>${esc(e.label)}</text>`;
        lastLabelX = flip ? Infinity : cx + 9 + lw + 6;
      }
    }
  });
  return out + '</svg>';
}
