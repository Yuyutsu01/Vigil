'use client';

import React, { useEffect, useState } from 'react';
import {
  Repository,
  RepositoryReviewResponse,
  disconnectRepository,
  getConnectURL,
  listRepositories,
} from '../lib/api';
import { PolicyEditor } from './PolicyEditor';
import { TriggerReview } from './TriggerReview';

interface RepositoriesListProps {
  token: string;
  onReviewTriggered?: (resp: RepositoryReviewResponse) => void;
}

export const RepositoriesList: React.FC<RepositoriesListProps> = ({ token, onReviewTriggered }) => {
  const [repos, setRepos] = useState<Repository[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const [selectedRepoForPolicy, setSelectedRepoForPolicy] = useState<Repository | null>(null);
  const [selectedRepoForReview, setSelectedRepoForReview] = useState<Repository | null>(null);

  const loadRepos = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listRepositories(token);
      setRepos(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load repositories');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRepos();
  }, [token]);

  const handleConnect = async () => {
    try {
      const { install_url } = await getConnectURL(token);
      window.location.href = install_url;
    } catch (err: any) {
      setError(err.message || 'Failed to initiate GitHub connection');
    }
  };

  const handleDisconnect = async (repoId: string) => {
    if (!confirm('Are you sure you want to disconnect this repository locally?')) return;
    try {
      await disconnectRepository(token, repoId);
      await loadRepos();
    } catch (err: any) {
      setError(err.message || 'Failed to disconnect repository');
    }
  };

  return (
    <div style={{ marginTop: 24 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 20, color: '#f8fafc' }}>Connected Repositories (FR-103)</h2>
          <p style={{ margin: '4px 0 0', fontSize: 13, color: '#94a3b8' }}>
            GitHub App repository integrations with scoped read-only analysis
          </p>
        </div>
        <button
          onClick={handleConnect}
          style={{
            padding: '10px 18px',
            background: '#238636',
            color: '#fff',
            border: 'none',
            borderRadius: 6,
            fontWeight: 600,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
          }}
        >
          <span>Connect GitHub App</span>
        </button>
      </div>

      {error && (
        <div style={{ background: '#7f1d1d', color: '#fecaca', padding: '10px 14px', borderRadius: 6, marginBottom: 16 }}>
          {error}
        </div>
      )}

      {loading ? (
        <div style={{ padding: 40, textAlign: 'center', color: '#64748b' }}>Loading repositories...</div>
      ) : repos.length === 0 ? (
        <div style={{
          padding: 48,
          textAlign: 'center',
          background: '#0f172a',
          border: '1px dashed #334155',
          borderRadius: 8,
          color: '#94a3b8',
        }}>
          <p style={{ margin: 0, fontSize: 15 }}>No GitHub repositories connected yet.</p>
          <p style={{ margin: '6px 0 16px', fontSize: 13, color: '#64748b' }}>
            Click &quot;Connect GitHub App&quot; to authorize repository access.
          </p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {repos.map(repo => (
            <div
              key={repo.repository_id}
              style={{
                background: '#1e293b',
                border: '1px solid #334155',
                borderRadius: 8,
                padding: 16,
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}
            >
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{ fontSize: 16, fontWeight: 600, color: '#f8fafc' }}>
                    {repo.full_name}
                  </span>
                  <span style={{
                    fontSize: 11,
                    padding: '2px 8px',
                    borderRadius: 4,
                    background: repo.is_connected ? '#064e3b' : '#7f1d1d',
                    color: repo.is_connected ? '#6ee7b7' : '#fca5a5',
                  }}>
                    {repo.is_connected ? 'Connected' : 'Disconnected'}
                  </span>
                </div>
                <div style={{ fontSize: 12, color: '#94a3b8', marginTop: 4 }}>
                  Default Branch: <code>{repo.default_branch}</code> &nbsp;|&nbsp;
                  Auto-PR: {repo.policy?.auto_review_on_pr ? 'Enabled' : 'Disabled'} &nbsp;|&nbsp;
                  Max files: {repo.policy?.max_files_per_review ?? 500}
                </div>
              </div>

              <div style={{ display: 'flex', gap: 8 }}>
                <button
                  onClick={() => setSelectedRepoForReview(repo)}
                  style={{
                    padding: '6px 14px',
                    background: '#0284c7',
                    color: '#fff',
                    border: 'none',
                    borderRadius: 6,
                    fontSize: 13,
                    fontWeight: 500,
                    cursor: 'pointer',
                  }}
                >
                  Review Ref
                </button>
                <button
                  onClick={() => setSelectedRepoForPolicy(repo)}
                  style={{
                    padding: '6px 14px',
                    background: '#334155',
                    color: '#e2e8f0',
                    border: 'none',
                    borderRadius: 6,
                    fontSize: 13,
                    cursor: 'pointer',
                  }}
                >
                  Policy
                </button>
                <button
                  onClick={() => handleDisconnect(repo.repository_id)}
                  style={{
                    padding: '6px 14px',
                    background: 'transparent',
                    color: '#ef4444',
                    border: '1px solid #7f1d1d',
                    borderRadius: 6,
                    fontSize: 13,
                    cursor: 'pointer',
                  }}
                >
                  Disconnect
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {selectedRepoForPolicy && (
        <PolicyEditor
          token={token}
          repo={selectedRepoForPolicy}
          onClose={() => setSelectedRepoForPolicy(null)}
          onSaved={() => {
            loadRepos();
            setSelectedRepoForPolicy(null);
          }}
        />
      )}

      {selectedRepoForReview && (
        <TriggerReview
          token={token}
          repo={selectedRepoForReview}
          onClose={() => setSelectedRepoForReview(null)}
          onStarted={resp => {
            setSelectedRepoForReview(null);
            if (onReviewTriggered) onReviewTriggered(resp);
          }}
        />
      )}
    </div>
  );
};
