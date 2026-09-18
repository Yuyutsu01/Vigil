'use client';

import React, { useEffect, useState } from 'react';
import {
  CostPreviewResponse,
  Repository,
  RepositoryReviewResponse,
  previewCost,
  triggerRepoReview,
} from '../lib/api';

interface TriggerReviewProps {
  token: string;
  repo: Repository;
  onClose: () => void;
  onStarted: (reviewResp: RepositoryReviewResponse) => void;
}

export const TriggerReview: React.FC<TriggerReviewProps> = ({
  token,
  repo,
  onClose,
  onStarted,
}) => {
  const [refType, setRefType] = useState<string>('branch');
  const [refValue, setRefValue] = useState<string>(repo.default_branch || 'main');
  const [scopeMode, setScopeMode] = useState<string>('full_repo');
  const [dirFilter, setDirFilter] = useState<string>('');
  const [costPreview, setCostPreview] = useState<CostPreviewResponse | null>(null);
  const [loadingPreview, setLoadingPreview] = useState<boolean>(false);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch cost preview on ref/scope change (C1)
  useEffect(() => {
    let active = true;
    async function loadPreview() {
      setLoadingPreview(true);
      setError(null);
      try {
        const preview = await previewCost(token, repo.repository_id, {
          ref_type: refType,
          ref_value: refValue,
          scope_mode: scopeMode,
          directory_filter: dirFilter || undefined,
        });
        if (active) setCostPreview(preview);
      } catch (err: any) {
        if (active) setError(err.message || 'Cost preview unavailable');
      } finally {
        if (active) setLoadingPreview(false);
      }
    }

    const t = setTimeout(loadPreview, 400);
    return () => {
      active = false;
      clearTimeout(t);
    };
  }, [token, repo.repository_id, refType, refValue, scopeMode, dirFilter]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      const resp = await triggerRepoReview(token, repo.repository_id, {
        ref_type: refType,
        ref_value: refValue,
        scope_mode: scopeMode,
        directory_filter: dirFilter || undefined,
      });
      onStarted(resp);
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to trigger repository review');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div style={{
      position: 'fixed',
      top: 0, left: 0, right: 0, bottom: 0,
      background: 'rgba(15, 23, 42, 0.8)',
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
        maxWidth: 520,
        boxShadow: '0 20px 25px -5px rgba(0,0,0,0.5)',
        border: '1px solid #334155',
      }}>
        <h2 style={{ marginTop: 0, fontSize: 18, color: '#38bdf8' }}>
          Trigger Scoped Review: {repo.full_name}
        </h2>

        {error && (
          <div style={{ background: '#7f1d1d', color: '#fecaca', padding: '8px 12px', borderRadius: 6, marginBottom: 16 }}>
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 12, marginBottom: 14 }}>
            <div>
              <label style={{ display: 'block', fontSize: 12, color: '#94a3b8', marginBottom: 4 }}>
                Reference Type:
              </label>
              <select
                value={refType}
                onChange={e => setRefType(e.target.value)}
                style={{ width: '100%', padding: '8px', background: '#0f172a', border: '1px solid #334155', borderRadius: 6, color: '#fff' }}
              >
                <option value="branch">Branch</option>
                <option value="commit">Commit SHA</option>
                <option value="pr">Pull Request</option>
                <option value="directory">Directory</option>
              </select>
            </div>
            <div>
              <label style={{ display: 'block', fontSize: 12, color: '#94a3b8', marginBottom: 4 }}>
                Target Ref / Value:
              </label>
              <input
                type="text"
                value={refValue}
                onChange={e => setRefValue(e.target.value)}
                placeholder={refType === 'pr' ? '42' : 'main'}
                style={{ width: '100%', padding: '8px', background: '#0f172a', border: '1px solid #334155', borderRadius: 6, color: '#fff' }}
              />
            </div>
          </div>

          <div style={{ marginBottom: 14 }}>
            <label style={{ display: 'block', fontSize: 12, color: '#94a3b8', marginBottom: 4 }}>
              Scope Mode:
            </label>
            <select
              value={scopeMode}
              onChange={e => setScopeMode(e.target.value)}
              style={{ width: '100%', padding: '8px', background: '#0f172a', border: '1px solid #334155', borderRadius: 6, color: '#fff' }}
            >
              <option value="full_repo">Full Repository (snapshot)</option>
              <option value="changed_files">Changed Files Only (diff)</option>
              <option value="directory">Directory Subtree</option>
            </select>
          </div>

          {scopeMode === 'directory' && (
            <div style={{ marginBottom: 14 }}>
              <label style={{ display: 'block', fontSize: 12, color: '#94a3b8', marginBottom: 4 }}>
                Subtree Directory Filter:
              </label>
              <input
                type="text"
                value={dirFilter}
                onChange={e => setDirFilter(e.target.value)}
                placeholder="backend/app"
                style={{ width: '100%', padding: '8px', background: '#0f172a', border: '1px solid #334155', borderRadius: 6, color: '#fff' }}
              />
            </div>
          )}

          {/* Pre-flight Cost Estimation Card (C1) */}
          <div style={{
            background: '#0f172a',
            border: '1px solid #334155',
            borderRadius: 8,
            padding: 14,
            marginBottom: 20,
          }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: '#94a3b8', marginBottom: 6 }}>
              Pre-flight Cost & Scope Estimate (C1)
            </div>
            {loadingPreview ? (
              <div style={{ color: '#64748b', fontSize: 12 }}>Estimating cost...</div>
            ) : costPreview ? (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, fontSize: 12 }}>
                <div>
                  <div style={{ color: '#64748b' }}>Files</div>
                  <div style={{ fontSize: 16, fontWeight: 'bold', color: '#f8fafc' }}>{costPreview.file_count}</div>
                </div>
                <div>
                  <div style={{ color: '#64748b' }}>Tokens (est)</div>
                  <div style={{ fontSize: 16, fontWeight: 'bold', color: '#f8fafc' }}>
                    {(costPreview.estimated_input_tokens + costPreview.estimated_output_tokens).toLocaleString()}
                  </div>
                </div>
                <div>
                  <div style={{ color: '#64748b' }}>Estimated Cost</div>
                  <div style={{
                    fontSize: 16,
                    fontWeight: 'bold',
                    color: costPreview.exceeds_cap ? '#ef4444' : '#22c55e',
                  }}>
                    ${costPreview.estimated_cost_usd.toFixed(4)}
                  </div>
                </div>
              </div>
            ) : (
              <div style={{ color: '#64748b', fontSize: 12 }}>Ready to estimate.</div>
            )}
            {costPreview?.exceeds_cap && (
              <div style={{ color: '#f87171', fontSize: 12, marginTop: 6 }}>
                Warning: Estimated cost exceeds ${costPreview.cost_cap_usd.toFixed(2)} cap. Review will pause if cap reached.
              </div>
            )}
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
              disabled={submitting}
              style={{ padding: '8px 20px', borderRadius: 6, background: '#10b981', color: '#fff', border: 'none', cursor: 'pointer', fontWeight: 600 }}
            >
              {submitting ? 'Starting...' : 'Start Review'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
