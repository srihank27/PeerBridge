import { useEffect, useId, useRef, type ReactNode } from 'react';
import { ArrowUpRight, Check, Sparkles, X, Zap, Shield, Orbit, Rocket } from 'lucide-react';
import type { JsonValue, Resource, Scores } from './types';

import { label } from './topics';
export { label } from './topics';
export const SLOTS = ['Mon 16:00', 'Tue 16:00', 'Wed 16:00', 'Thu 16:00', 'Fri 16:00', 'Sat 10:00'];
export const PREFERENCES = [{ id: 'step_by_step', label: 'Step by step' }, { id: 'practice', label: 'Practice together' }, { id: 'encouragement', label: 'Encouragement' }];
export const pct = (value: number) => `${Math.round(value * 100)}%`;
export function date(value: string) { const d = new Date(/^\d{4}-\d{2}-\d{2}$/.test(value) ? `${value}T12:00:00` : value.endsWith('Z') || /[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`); return Number.isNaN(d.getTime()) ? value : d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }); }
export function Avatar({ variant = 'bolt', size = 'normal', alias = '' }: { variant?: string; size?: 'small' | 'normal' | 'large'; alias?: string }) {
  const Icon = variant === 'shield' ? Shield : variant === 'orbit' ? Orbit : variant === 'comet' ? Rocket : Zap;
  return <span className={`avatar avatar-${variant} avatar-${size}`} role="img" aria-label={`${alias ? `${alias}'s ` : ''}${variant} hero avatar`}><Icon aria-hidden="true" strokeWidth={1.8} /></span>;
}
export function Badge({ children, tone = 'neutral' }: { children: ReactNode; tone?: string }) { return <span className={`badge badge-${tone}`}>{children}</span>; }
export function Empty({ title, children, action }: { title: string; children: ReactNode; action?: ReactNode }) { return <div className="empty"><span className="empty-icon"><Sparkles size={24} /></span><h3>{title}</h3><p>{children}</p>{action}</div>; }
export function Spinner({ text = 'Loading your hero network…' }: { text?: string }) { return <div className="loading" role="status"><span className="spinner" />{text}</div>; }
export function Modal({ title, eyebrow, children, onClose, wide = false }: { title: string; eyebrow?: string; children: ReactNode; onClose: () => void; wide?: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  const id = useId();
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const node = ref.current!;
    const focusables = () => Array.from(node.querySelectorAll<HTMLElement>('button:not(:disabled), [href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex="0"]'));
    (focusables()[0] || node).focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') closeRef.current();
      if (event.key === 'Tab') { const items = focusables(); const first = items[0]; const last = items[items.length - 1]; if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); } else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); } }
    };
    document.addEventListener('keydown', onKey);
    return () => { document.removeEventListener('keydown', onKey); document.body.style.overflow = previousOverflow; previous?.focus(); };
  }, []);
  return <div className="modal-backdrop" onMouseDown={e => { if (e.target === e.currentTarget) onClose(); }}><div ref={ref} className={`modal ${wide ? 'modal-wide' : ''}`} role="dialog" aria-modal="true" aria-labelledby={id} tabIndex={-1}><div className="modal-heading"><div>{eyebrow && <span className="eyebrow">{eyebrow}</span>}<h2 id={id}>{title}</h2></div><button className="icon-button" type="button" onClick={onClose} aria-label="Close dialog"><X /></button></div>{children}</div></div>;
}
export function ResourceCard({ resource }: { resource: Resource }) {
  let hostname = 'Verified resource'; try { hostname = new URL(resource.url).hostname.replace('www.', ''); } catch { /* Keep human readable fallback. */ }
  return <article className="resource-card"><div className="resource-topline"><span className="resource-mark">{hostname.slice(0, 1).toUpperCase()}</span><Badge tone="green"><Check size={11} /> Directory link</Badge></div><h3>{resource.title}</h3><p>{resource.access_notes}</p><div className="tag-row">{resource.topics.map(t => <span className="topic-tag" key={t}>{label(t)}</span>)}</div><div className="resource-footer"><span>Verified {resource.verified_at.slice(0, 10)}</span><a href={resource.url} target="_blank" rel="noreferrer">Open resource <ArrowUpRight size={15} /><span className="sr-only"> (opens a new tab)</span></a></div></article>;
}
export function ScoreBreakdown({ scores }: { scores: Scores }) {
  const items: [keyof Scores, string, string][] = [['S', 'Topic relevance', '40% weight'], ['A', 'Availability overlap', '25% weight'], ['C', 'Support preference', '20% weight'], ['F', 'Remaining capacity', '15% weight']];
  return <div className="score-breakdown">{items.map(([key, name, weight]) => <div className="score-row" key={key}><div><span>{name}</span><small>{weight}</small></div><div className="score-track"><span style={{ width: pct(scores[key]) }} /></div><strong>{pct(scores[key])}</strong></div>)}</div>;
}
export function DataTree({ value, depth = 0 }: { value: JsonValue; depth?: number }) {
  if (value === null) return <span className="data-null">Not available</span>;
  if (typeof value === 'boolean') return <Badge tone={value ? 'green' : 'neutral'}>{value ? 'Yes' : 'No'}</Badge>;
  if (typeof value === 'number') return <strong className="data-number">{Number.isInteger(value) ? value.toLocaleString() : Number(value.toFixed(4)).toLocaleString()}</strong>;
  if (typeof value === 'string') return <span>{value || '—'}</span>;
  if (Array.isArray(value)) return value.length ? <div className="data-array">{value.map((item, i) => <div key={i} className="data-array-item"><DataTree value={item} depth={depth + 1} /></div>)}</div> : <span className="data-null">None</span>;
  return <dl className={`data-tree data-depth-${Math.min(depth, 3)}`}>{Object.entries(value).map(([key, item]) => <div key={key} className={`data-entry ${typeof item === 'object' && item !== null ? 'data-nested' : ''}`}><dt>{label(key)}</dt><dd><DataTree value={item} depth={depth + 1} /></dd></div>)}</dl>;
}
type JsonObject = { [key: string]: JsonValue };
const object = (value: JsonValue | undefined): JsonObject => typeof value === 'object' && value !== null && !Array.isArray(value) ? value : {};
function Ratio({ value }: { value: JsonValue | undefined }) { const r = object(value); return typeof r.value === 'number' ? <><strong>{pct(r.value)}</strong><small>{String(r.numerator ?? '—')} / {String(r.denominator ?? '—')}</small></> : <span>Not measured</span>; }
export function EvaluationSummary({ value }: { value: JsonValue }) {
  const root = object(value); const matching = object(root.matching); const assignment = object(root.assignment); const dataset = object(root.dataset);
  return <div className="evaluation-summary"><div className="evaluation-caption"><Badge tone="purple">Actual run · Synthetic data</Badge><span>{String(dataset.evaluation_count ?? '—')} held-out requests · {String(dataset.calibration_count ?? '—')} calibration requests</span></div><div className="table-scroll"><table className="metrics-table"><caption>Recommendation comparison</caption><thead><tr><th scope="col">Method</th><th scope="col">Coverage</th><th scope="col">Top-three relevance</th><th scope="col">Top-three hit rate</th></tr></thead><tbody>{['keyword', 'semantic'].map(mode => { const result = object(matching[mode]); const evaluation = object(result.evaluation); return <tr key={mode}><th scope="row">{label(mode)}</th>{result.available === true ? <><td><Ratio value={evaluation.coverage} /></td><td><Ratio value={evaluation.top_three_relevance} /></td><td><Ratio value={evaluation.top_three_hit_rate} /></td></> : <td colSpan={3} className="unavailable-metric">Not run. {String(result.reason || 'This mode was unavailable.')}</td>}</tr>; })}</tbody></table></div><div className="table-scroll"><table className="metrics-table"><caption>Assignment simulation</caption><thead><tr><th scope="col">Planner</th><th scope="col">Assigned</th><th scope="col">Coverage</th><th scope="col">Mean served wait</th><th scope="col">Maximum workload</th></tr></thead><tbody>{['batch', 'greedy'].map(mode => { const result = object(assignment[mode]); const waiting = object(result.waiting); const workload = object(result.workload); return <tr key={mode}><th scope="row">{mode === 'batch' ? 'Capacity-aware batch' : 'Greedy baseline'}</th><td><strong>{String(result.assigned_count ?? '—')}</strong></td><td><Ratio value={result.coverage} /></td><td>{typeof waiting.served_wait_hours_mean === 'number' ? `${waiting.served_wait_hours_mean.toFixed(1)} h` : 'Not measured'}</td><td>{String(workload.maximum_projected_load ?? '—')} assignments</td></tr>; })}</tbody></table></div><p className="evaluation-help">Ratios show the measured numerator and denominator. Waiting times are fixed synthetic hours, and workload includes existing assignments. Inspect the full results for definitions, calibration, per-request outcomes, and workload distribution.</p></div>;
}
export function HeroArtwork() {
  return <svg viewBox="0 0 430 330" className="hero-artwork" role="img" aria-label="Original PeerBridge heroes joining forces around a glowing bridge"><defs><linearGradient id="cape" x1="0" x2="1"><stop stopColor="#9a85ff"/><stop offset="1" stopColor="#5f45df"/></linearGradient><linearGradient id="suit" x1="0" y1="0" x2="1" y2="1"><stop stopColor="#77dcff"/><stop offset="1" stopColor="#4474f4"/></linearGradient><linearGradient id="bridge" x1="0" x2="1"><stop stopColor="#7290ff" stopOpacity="0"/><stop offset=".5" stopColor="#c8e9ff"/><stop offset="1" stopColor="#7290ff" stopOpacity="0"/></linearGradient></defs><circle cx="229" cy="161" r="126" fill="#fff" opacity=".045"/><circle cx="229" cy="161" r="104" stroke="#b9baff" strokeDasharray="4 10" fill="none" opacity=".22"/><path d="M41 263 Q217 213 394 263" fill="none" stroke="url(#bridge)" strokeWidth="3"/><path d="M88 278h284M119 291h222" stroke="#99baff" opacity=".13" strokeWidth="2"/><g transform="translate(120,38)"><path d="M77 115 43 239 142 222 126 115" fill="url(#cape)"/><path d="m80 116-14 61 18 24 4 43h21l5-44 14-37-13-47" fill="#273d9c"/><path d="m85 183-2 60-16 13h38l5-68M111 180l7 57 15 9h-28l-11-62" fill="#182760"/><path d="m80 112-20 13-22 53 16 10 28-42M117 116l19 12 28 38-15 11-32-31" fill="url(#suit)"/><path d="m79 111-8 60 28 22 28-22-9-60" fill="url(#suit)"/><path d="m98 126-13 24h13l-5 18 21-29h-14l9-13" fill="#f4eeff"/><rect x="88" y="94" width="22" height="25" rx="10" fill="#d6b0ff"/><ellipse cx="99" cy="76" rx="28" ry="34" fill="#e5baff"/><path d="M71 74c-6-42 41-51 58-18l-13 2-8-12-6 16-27 11" fill="#1b285c"/><path d="m72 70 14-7 14 7 15-7 12 7-4 15-22-4-20 4" fill="#4b3cc3"/><path d="m83 73 10 1m14 0 10-1" stroke="#fff" strokeWidth="3" strokeLinecap="round"/><path d="m96 93 10 0" stroke="#a05db1" strokeWidth="2" strokeLinecap="round"/><path d="M47 181q-13-2-12 9 9 15 19 3M151 168q9-12 17-4 10 12-4 19" fill="#e5baff"/></g><g transform="translate(268,128) rotate(9)"><path d="M10 64-9 137l70-8-20-63" fill="#5e7bf0"/><path d="m14 65-9 39 16 21-3 34h16l8-35 8-27-12-33" fill="#6653c8"/><path d="m19 121-6 34-9 7h27l5-38m-3-3 5 31 10 8H31l-9-33" fill="#1d285b"/><path d="m14 65-16 7-16 31 12 6 22-25m23-18 15 10 18 19-10 11-24-23" fill="#aba4ff"/><path d="m13 63-5 41 21 16 21-17-11-40" fill="#aaa0ff"/><path d="m27 76 14 4-2 14-10 8-11-8-1-14" fill="#e1e6ff"/><rect x="20" y="50" width="16" height="17" rx="5" fill="#92d9ef"/><ellipse cx="28" cy="36" rx="22" ry="26" fill="#b3e6f6"/><path d="M7 32Q2 9 25 8q23-1 25 24l-13-7-9-7-9 9Z" fill="#243665"/><path d="m8 32 18-5 22 5-3 12-17-3-17 3" fill="#3e58af"/><path d="m15 35 8 0m11 0h8" stroke="#fff" strokeWidth="2" strokeLinecap="round"/><path d="m-10 103-7 6m83-8 5 6" stroke="#b3e6f6" strokeWidth="10" strokeLinecap="round"/></g><g fill="#c7d7ff"><path d="m80 95 3 8 8 3-8 3-3 8-3-8-8-3 8-3ZM342 62l3 9 9 3-9 3-3 9-3-9-9-3 9-3Z"/><circle cx="362" cy="196" r="3"/><circle cx="102" cy="231" r="3"/><circle cx="143" cy="63" r="2"/></g><g transform="translate(76,156) rotate(-14)"><rect width="53" height="53" rx="15" fill="#fff" fillOpacity=".13" stroke="#fff" strokeOpacity=".2"/><path d="m30 11-15 18h12l-4 14 16-21H27Z" fill="#cecbff"/></g></svg>;
}
