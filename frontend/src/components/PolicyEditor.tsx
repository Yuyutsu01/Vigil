'use client';

import React, { useState } from 'react';
import { Repository, RepositoryPolicy, updateRepositoryPolicy } from '../lib/api';

interface PolicyEditorProps {
  token: string;
  repo: Repository;
  onClose: () => void;
  onSaved: (updatedPolicy: RepositoryPolicy) => void;
}

export const PolicyEditor: React.FC<PolicyEditorProps> = ({ token, repo, onClose, onSaved }) => {
  const currentPolicy = repo.policy || {
    enabled_languages: ['python', 'javascript', 'typescript'],
    ignored_paths: ['vendor/**', 'node_modules/**', '.git/**'],
    ignored_rules: [],
    max_files_per_review: 500,
    auto_review_on_push: false,
    auto_review_on_pr: true,
    review_fork_prs: false,
    review_draft_prs: false,
  };

  const [languages, setLanguages] = useState<string>(currentPolicy.enabled_languages.join(', '));
  const [ignoredPaths, setIgnoredPaths] = useState<string>(currentPolicy.ignored_paths.join('\n'));
  const [maxFiles, setMaxFiles] = useState<number>(currentPolicy.max_files_per_review);
  const [autoReviewPR, setAutoReviewPR] = useState<boolean>(currentPolicy.auto_review_on_pr);
  const [autoReviewPush, setAutoReviewPush] = useState<boolean>(currentPolicy.auto_review_on_push);
  const [reviewForkPRs, setReviewForkPRs] = useState<boolean>(currentPolicy.review_fork_prs);
  const [reviewDraftPRs, setReviewDraftPRs] = useState<boolean>(currentPolicy.review_draft_prs);
  const [saving, setSaving] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);

    const payload: Partial<RepositoryPolicy> = {
      enabled_languages: languages.split(',').map(s => s.trim().toLowerCase()).filter(Boolean),
      ignored_paths: ignoredPaths.split('\n').map(s => s.trim()).filter(Boolean),
      max_files_per_review: Number(maxFiles),
      auto_review_on_pr: autoReviewPR,
      auto_review_on_push: autoReviewPush,
      review_fork_prs: reviewForkPRs,
      review_draft_prs: reviewDraftPRs,
    };

    try {
      const updated = await updateRepositoryPolicy(token, repo.repository_id, payload);
      onSaved(updated);
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to update policy');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{
      position: 'fixed',
      top: 0, left: 0, right: 0, bottom: 0,
      background: 'rgba(15, 23, 42, 0.75)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      zIndex: 1000,
      backdropFilter: 'blur(4px)',
    }}>
      <div style={{
        background: '#1e293b',
        color: '#f8fafc',
        borderRadius: 12,
        padding: 28,
        width: '90%',
        maxWidth: 560,
        boxShadow: '0 20px 25px -5px rgba(0,0,0,0.5)',
        border: '1px solid #334155',
      }}>
        <h2 style={{ marginTop: 0, fontSize: 18, color: '#38bdf8' }}>
          Repository Policy: {repo.full_name}
        </h2>

        {error && (
          <div style={{ background: '#7f1d1d', color: '#fecaca', padding: '8px 12px', borderRadius: 6, marginBottom: 16 }}>
            {error}
          </div>
        )}

        <form onSubmit={handleSave}>
          <div style={{ marginBottom: 14 }}>
            <label style={{ display: 'block', fontSize: 12, color: '#94a3b8', marginBottom: 4 }}>
              Enabled Languages (comma-separated):
            </label>
            <input
              type="text"
              value={languages}
              onChange={e => setLanguages(e.target.value)}
              style={{ width: '100%', padding: '8px 10px', background: '#0f172a', border: '1px solid #334155', borderRadius: 6, color: '#fff' }}
            />
          </div>

          <div style={{ marginBottom: 14 }}>
            <label style={{ display: 'block', fontSize: 12, color: '#94a3b8', marginBottom: 4 }}>
              Ignored Path Globs (one per line):
            </label>
            <textarea
              rows={4}
              value={ignoredPaths}
              onChange={e => setIgnoredPaths(e.target.value)}
              style={{ width: '100%', padding: '8px 10px', background: '#0f172a', border: '1px solid #334155', borderRadius: 6, color: '#fff', fontFamily: 'monospace' }}
            />
          </div>

          <div style={{ marginBottom: 14 }}>
            <label style={{ display: 'block', fontSize: 12, color: '#94a3b8', marginBottom: 4 }}>
              Max Files Per Review:
            </label>
            <input
              type="number"
              min={1}
              max={1000}
              value={maxFiles}
              onChange={e => setMaxFiles(Number(e.target.value))}
              style={{ width: '100%', padding: '8px 10px', background: '#0f172a', border: '1px solid #334155', borderRadius: 6, color: '#fff' }}
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 20 }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: '#cbd5e1' }}>
              <input
                type="checkbox"
                checked={autoReviewPR}
                onChange={e => setAutoReviewPR(e.target.checked)}
              />
              Auto-review on PR
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: '#cbd5e1' }}>
              <input
                type="checkbox"
                checked={autoReviewPush}
                onChange={e => setAutoReviewPush(e.target.checked)}
              />
              Auto-review on Push
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: '#cbd5e1' }}>
              <input
                type="checkbox"
                checked={reviewForkPRs}
                onChange={e => setReviewForkPRs(e.target.checked)}
              />
              Review Fork PRs (H2)
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: '#cbd5e1' }}>
              <input
                type="checkbox"
                checked={reviewDraftPRs}
                onChange={e => setReviewDraftPRs(e.target.checked)}
              />
              Review Draft PRs (H3)
            </label>
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12 }}>
            <button
              type="button"
              onClick={onClose}
              style={{ padding: '8px 16px', borderRadius: 6, background: '#334155', color: '#fff', border: 'none', cursor: 'pointer' }}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              style={{ padding: '8px 20px', borderRadius: 6, background: '#0284c7', color: '#fff', border: 'none', cursor: 'pointer', fontWeight: 600 }}
            >
              {saving ? 'Saving...' : 'Save Policy'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
