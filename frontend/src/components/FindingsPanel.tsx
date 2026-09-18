'use client';

import { useState } from 'react';
import styles from './FindingsPanel.module.css';
import type { Finding, ReviewRun } from '../lib/api';
import { submitFeedback, deleteReview } from '../lib/api';

interface Props {
  run: ReviewRun;
  token: string;
  onDelete: () => void;
  onToast: (msg: string, type?: 'success' | 'error' | 'info') => void;
}

const SEV_ORDER: Record<string, number> = {
  Critical: 0, High: 1, Medium: 2, Low: 3, Info: 4,
};

function SeverityBadge({ sev }: { sev: string }) {
  const cls = `badge badge-${sev.toLowerCase()}`;
  return <span className={cls} aria-label={`Severity: ${sev}`}>{sev}</span>;
}

function OriginBadge({ origin }: { origin: string }) {
  const label = origin === 'rule' ? '⚙ Rule' : '🤖 AI';
  const color = origin === 'rule' ? 'rgba(59,130,246,0.15)' : 'rgba(139,92,246,0.15)';
  const border = origin === 'rule' ? 'rgba(59,130,246,0.3)' : 'rgba(139,92,246,0.3)';
  const textColor = origin === 'rule' ? '#93c5fd' : '#c4b5fd';
  return (
    <span className="badge" style={{ background: color, borderColor: border, color: textColor }}>
      {label}
    </span>
  );
}

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color = pct >= 80 ? '#22c55e' : pct >= 60 ? '#f59e0b' : '#94a3b8';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
      <div className="progress-bar" style={{ width: 64 }}>
        <div className="progress-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{pct}%</span>
    </div>
  );
}

function FindingCard({ f, token, onToast }: {
  f: Finding; token: string; onToast: Props['onToast'];
}) {
  const [expanded, setExpanded] = useState(false);
  const [disposition, setDisposition] = useState(f.status);
  const [submitting, setSubmitting] = useState(false);

  async function handleFeedback(d: string) {
    setSubmitting(true);
    try {
      await submitFeedback(token, f.run_id, f.finding_id, {
        disposition: d,
        useful: d !== 'false_positive',
      });
      setDisposition(d as any);
      onToast('Feedback recorded', 'success');
    } catch (e: any) {
      onToast(e.message, 'error');
    } finally {
      setSubmitting(false);
    }
  }

  const ev = f.evidence[0];
  const location = ev?.source_range?.start_line
    ? `Line ${ev.source_range.start_line}${ev.source_range.start_col ? `:${ev.source_range.start_col}` : ''}`
    : null;

  return (
    <article className={`${styles.card} ${styles[f.severity.toLowerCase()]} fade-in`}>
      {/* Card header */}
      <div className={styles.cardHeader}>
        <div className={styles.cardMeta}>
          <SeverityBadge sev={f.severity} />
          <OriginBadge origin={f.origin} />
          <ConfidenceBar value={f.confidence} />
          {f.rule_id && (
            <span className={styles.ruleId} title="Rule ID">{f.rule_id}</span>
          )}
          {location && (
            <span className={styles.location} title="Source location">{location}</span>
          )}
        </div>
        <button
          className={styles.expandBtn}
          onClick={() => setExpanded(v => !v)}
          aria-expanded={expanded}
          aria-controls={`finding-detail-${f.finding_id}`}
          aria-label={expanded ? 'Collapse finding' : 'Expand finding'}
        >
          {expanded ? '▲' : '▼'}
        </button>
      </div>

      <h3 className={styles.title}>{f.title}</h3>

      {expanded && (
        <div id={`finding-detail-${f.finding_id}`} className={styles.detail}>
          <hr />

          {/* Evidence excerpt */}
          {ev?.code_excerpt && (
            <div className={styles.section}>
              <h4>Evidence</h4>
              <pre className="code-block">{ev.code_excerpt}</pre>
              {ev.ast_path && (
                <p className="text-muted" style={{ fontSize: '0.75rem', marginTop: '0.3rem' }}>
                  AST path: <code>{ev.ast_path}</code>
                </p>
              )}
            </div>
          )}

          {/* Rationale */}
          <div className={styles.section}>
            <h4>Rationale</h4>
            <p className="text-secondary">{f.rationale}</p>
          </div>

          {/* Remediation */}
          <div className={styles.section}>
            <h4>Remediation</h4>
            <p className="text-secondary">{f.remediation}</p>
          </div>

          {/* Phase 1 note — no patch */}
          <p className={styles.noPatch}>
            ℹ Patch suggestions are deferred to Phase 3 (FR-105).
          </p>

          {/* Feedback */}
          <div className={styles.feedbackRow}>
            <span className="text-muted" style={{ fontSize: '0.8rem' }}>Disposition:</span>
            {(['accepted', 'rejected', 'false_positive'] as const).map(d => (
              <button
                key={d}
                id={`feedback-${f.finding_id}-${d}`}
                className={`btn btn-ghost ${styles.feedbackBtn} ${disposition === d ? styles.feedbackActive : ''}`}
                onClick={() => handleFeedback(d)}
                disabled={submitting}
                aria-pressed={disposition === d}
              >
                {d.replace('_', ' ')}
              </button>
            ))}
          </div>
        </div>
      )}
    </article>
  );
}

export default function FindingsPanel({ run, token, onDelete, onToast }: Props) {
  const [deleting, setDeleting] = useState(false);
  const [filter, setFilter] = useState<string>('all');

  const findings = [...run.findings].sort(
    (a, b) => (SEV_ORDER[a.severity] ?? 99) - (SEV_ORDER[b.severity] ?? 99)
  );
  const filtered = filter === 'all' ? findings : findings.filter(f => f.severity === filter);

  const counts: Record<string, number> = {};
  for (const f of findings) {
    counts[f.severity] = (counts[f.severity] || 0) + 1;
  }

  async function handleDelete() {
    if (!confirm('Delete this review and its source artifact? This cannot be undone.')) return;
    setDeleting(true);
    try {
      await deleteReview(token, run.run_id);
      onToast('Review deleted', 'success');
      onDelete();
    } catch (e: any) {
      onToast(e.message, 'error');
    } finally {
      setDeleting(false);
    }
  }

  const statusClass = {
    completed: 'status-completed',
    partial: 'status-completed',
    failed: 'status-failed',
    budget_paused: 'status-running',
    pending: 'status-pending',
    running: 'status-running',
    deleted: 'status-pending',
  }[run.status] || 'status-pending';

  return (
    <section className={styles.panel} aria-label="Review results">
      {/* Run summary */}
      <div className={styles.summary}>
        <div>
          <div className="flex items-center gap-2" style={{ marginBottom: '0.25rem' }}>
            <span className={`status-dot ${statusClass}`} aria-hidden="true" />
            <h2 style={{ fontSize: '1rem' }}>
              {run.status.charAt(0).toUpperCase() + run.status.slice(1)}
            </h2>
            {run.parked_reason && (
              <span className="badge badge-medium">{run.parked_reason}</span>
            )}
          </div>
          <p className="text-muted" style={{ fontSize: '0.75rem' }}>
            Run {run.run_id.slice(0, 8)}…
            {run.timing_ms && ` · ${run.timing_ms}ms`}
            {run.prompt_version && ` · prompt@${run.prompt_version.slice(0, 8)}`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* Severity summary chips */}
          {(['Critical', 'High', 'Medium', 'Low', 'Info'] as const).map(s =>
            counts[s] ? (
              <span key={s} className={`badge badge-${s.toLowerCase()}`}>
                {counts[s]} {s}
              </span>
            ) : null
          )}
          <button
            id="delete-review-btn"
            className="btn btn-danger"
            onClick={handleDelete}
            disabled={deleting}
            aria-label="Delete this review"
            style={{ marginLeft: '0.5rem' }}
          >
            {deleting ? <span className="spinner" /> : '🗑 Delete'}
          </button>
        </div>
      </div>

      {/* Filter bar */}
      {findings.length > 0 && (
        <div className={styles.filterBar} role="group" aria-label="Filter by severity">
          {(['all', 'Critical', 'High', 'Medium', 'Low', 'Info'] as const).map(s => (
            <button
              key={s}
              id={`filter-${s.toLowerCase()}`}
              className={`btn btn-ghost ${styles.filterBtn} ${filter === s ? styles.filterActive : ''}`}
              onClick={() => setFilter(s)}
            >
              {s === 'all' ? `All (${findings.length})` : `${s} (${counts[s] || 0})`}
            </button>
          ))}
        </div>
      )}

      {/* Findings list */}
      {filtered.length === 0 ? (
        <div className={styles.empty} role="status">
          {findings.length === 0
            ? '✅ No findings — code looks clean for the selected rules.'
            : `No ${filter} findings.`}
        </div>
      ) : (
        <div className={styles.list}>
          {filtered.map(f => (
            <FindingCard key={f.finding_id} f={f} token={token} onToast={onToast} />
          ))}
        </div>
      )}
    </section>
  );
}
