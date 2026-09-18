'use client';

import { useState, useCallback } from 'react';
import LoginForm from '../components/LoginForm';
import CodeEditor from '../components/CodeEditor';
import FindingsPanel from '../components/FindingsPanel';
import { RepositoriesList } from '../components/RepositoriesList';
import { getToken, clearToken } from '../lib/token';
import { getReview, type ReviewRun, type RepositoryReviewResponse } from '../lib/api';
import styles from './page.module.css';

type Toast = { msg: string; type: 'success' | 'error' | 'info'; id: number };

let toastSeq = 0;

type ActiveTab = 'editor' | 'repos';

export default function Home() {
  const [token, setToken] = useState<string | null>(() => {
    // Restore from sessionStorage on client hydration
    if (typeof window !== 'undefined') return getToken();
    return null;
  });
  const [run, setRun] = useState<ReviewRun | null>(null);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [activeTab, setActiveTab] = useState<ActiveTab>('editor');

  function showToast(msg: string, type: Toast['type'] = 'info') {
    const id = ++toastSeq;
    setToasts(t => [...t, { msg, type, id }]);
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 4000);
  }

  function handleLoginSuccess() {
    setToken(getToken());
  }

  function handleLogout() {
    clearToken();
    setToken(null);
    setRun(null);
  }

  function handleResult(r: ReviewRun) {
    setRun(r);
    const count = r.finding_count;
    if (r.status === 'completed' || r.status === 'partial') {
      showToast(
        count === 0
          ? '✅ Analysis complete — no findings.'
          : `⚠ Analysis complete — ${count} finding${count > 1 ? 's' : ''} detected.`,
        count === 0 ? 'success' : 'info'
      );
    } else if (r.status === 'failed') {
      showToast('Analysis failed: ' + (r.error_message || 'Unknown error'), 'error');
    }
  }

  async function handleRepoReviewTriggered(resp: RepositoryReviewResponse) {
    showToast(`Repository review started (${resp.scope_mode})`, 'info');
    if (token) {
      try {
        const runData = await getReview(token, resp.review_run_id);
        setRun(runData);
        setActiveTab('editor');
      } catch (err: any) {
        showToast(err.message || 'Failed to fetch review run', 'error');
      }
    }
  }

  function handleError(msg: string) {
    showToast(msg, 'error');
  }

  // Not logged in → show login screen
  if (!token) {
    return <LoginForm onSuccess={handleLoginSuccess} />;
  }

  return (
    <div className={styles.root}>
      {/* ── Navigation ──────────────────────────────────────────────────── */}
      <nav className={styles.nav} role="navigation" aria-label="Primary navigation">
        <div className={styles.navBrand}>
          <svg width="28" height="28" viewBox="0 0 36 36" fill="none" aria-hidden="true">
            <circle cx="18" cy="18" r="18" fill="rgba(245,158,11,0.12)" />
            <path d="M18 8L26 14v8l-8 6-8-6v-8L18 8z" stroke="#f59e0b" strokeWidth="1.5" fill="none" />
            <circle cx="18" cy="18" r="3" fill="#f59e0b" />
          </svg>
          <span className={styles.navTitle}>Vigil</span>
          <span className={styles.navPhase}>Phase 3</span>
        </div>
        <div className={styles.navRight}>
          <div style={{ display: 'flex', gap: 6, marginRight: 16 }}>
            <button
              onClick={() => setActiveTab('editor')}
              style={{
                padding: '6px 14px',
                borderRadius: 6,
                border: 'none',
                background: activeTab === 'editor' ? '#f59e0b' : '#334155',
                color: activeTab === 'editor' ? '#000' : '#fff',
                fontWeight: 600,
                fontSize: 13,
                cursor: 'pointer',
              }}
            >
              Single File Review
            </button>
            <button
              onClick={() => setActiveTab('repos')}
              style={{
                padding: '6px 14px',
                borderRadius: 6,
                border: 'none',
                background: activeTab === 'repos' ? '#f59e0b' : '#334155',
                color: activeTab === 'repos' ? '#000' : '#fff',
                fontWeight: 600,
                fontSize: 13,
                cursor: 'pointer',
              }}
            >
              GitHub Repositories
            </button>
          </div>
          <span className={styles.navHint}>
            🔒 Code is never executed
          </span>
          <button
            id="logout-btn"
            className="btn btn-ghost"
            onClick={handleLogout}
            style={{ fontSize: '0.8rem', padding: '0.4rem 0.8rem' }}
          >
            Sign out
          </button>
        </div>
      </nav>

      {/* ── Main content ─────────────────────────────────────────────────── */}
      <main className={styles.main} id="main-content">
        <div className="container">
          {activeTab === 'repos' ? (
            <RepositoriesList
              token={token}
              onReviewTriggered={handleRepoReviewTriggered}
            />
          ) : (
            <div className={styles.grid}>
              {/* Left — editor */}
              <div className={styles.editorCol}>
                <h2 className={styles.sectionLabel}>
                  <span>1</span> Paste Source Code
                </h2>
                <CodeEditor
                  token={token}
                  onResult={handleResult}
                  onError={handleError}
                />
              </div>

            {/* Right — results */}
            <div className={styles.resultsCol}>
              <h2 className={styles.sectionLabel}>
                <span>2</span> Review Findings
              </h2>
              {run ? (
                <FindingsPanel
                  run={run}
                  token={token}
                  onDelete={() => setRun(null)}
                  onToast={showToast}
                />
              ) : (
                <div className={styles.placeholder} role="status" aria-live="polite">
                  <svg width="48" height="48" viewBox="0 0 48 48" fill="none" aria-hidden="true">
                    <circle cx="24" cy="24" r="24" fill="rgba(139,92,246,0.08)" />
                    <path d="M24 14l8 5v10l-8 5-8-5V19l8-5z" stroke="rgba(139,92,246,0.5)" strokeWidth="1.5" fill="none" />
                    <circle cx="24" cy="24" r="3" fill="rgba(139,92,246,0.5)" />
                  </svg>
                  <p>Submit code for analysis to see findings here.</p>
                  <p className="text-muted" style={{ fontSize: '0.8rem', marginTop: '0.25rem' }}>
                    Supports Python · JavaScript · TypeScript · up to 250 KB
                  </p>
                </div>
              )}
            </div>
          </div>
          )}
        </div>
      </main>

      {/* ── Toasts ───────────────────────────────────────────────────────── */}
      <div role="region" aria-live="polite" aria-label="Notifications">
        {toasts.map(t => (
          <div key={t.id} className={`toast toast-${t.type}`} role="alert">
            {t.msg}
          </div>
        ))}
      </div>
    </div>
  );
}
