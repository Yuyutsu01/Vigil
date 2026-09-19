'use client';

import React, { useEffect, useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import {
  Github,
  GitBranch,
  Play,
  Trash2,
  AlertCircle,
  RefreshCw,
  Plus,
  Loader2,
  CheckCircle2,
  Shield,
  Clock,
} from 'lucide-react';
import { api } from '@/lib/api';
import { Repository } from '@/lib/types';
import { focusRing } from '@/lib/styles';

interface GitHubViewProps {
  onSelectReview?: (reviewId: string) => void;
}

interface RepositoryCardProps {
  repo: Repository;
  onTriggerReview: () => void;
  onDisconnect: () => void;
  triggering: boolean;
  disconnecting: boolean;
}

function RepositoryCard({
  repo,
  onTriggerReview,
  onDisconnect,
  triggering,
  disconnecting,
}: RepositoryCardProps) {
  const isConnected = repo.is_connected ?? repo.is_active ?? true;
  const repoName = repo.full_name || repo.repo_name || 'Unnamed Repository';
  const defaultBranch = repo.default_branch || 'main';

  return (
    <div className="p-5 rounded-xl border border-white/10 bg-white/[0.02] hover:bg-white/[0.04] transition-all duration-200 flex flex-col md:flex-row md:items-center justify-between gap-4">
      {/* Repository Details */}
      <div className="flex items-start gap-3.5">
        <div className="p-2.5 rounded-xl bg-white/5 border border-white/10 shrink-0 text-white/80">
          <Github className="w-5 h-5" aria-hidden="true" />
        </div>
        <div>
          <div className="flex items-center gap-2.5 flex-wrap">
            <h3 className="font-semibold text-sm text-white hover:text-cyan-400 transition-colors">
              {repoName}
            </h3>
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-white/5 border border-white/10 text-[11px] font-mono text-zinc-300">
              <GitBranch className="w-3 h-3 text-white/50" aria-hidden="true" />
              {defaultBranch}
            </span>
            <span
              role="status"
              aria-label={isConnected ? 'Active' : 'Paused'}
              className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-mono ${
                isConnected
                  ? 'bg-emerald-500/10 border border-emerald-500/30 text-emerald-400'
                  : 'bg-zinc-500/10 border border-zinc-500/30 text-zinc-400'
              }`}
            >
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  isConnected ? 'bg-emerald-400 animate-pulse' : 'bg-zinc-500'
                }`}
                aria-hidden="true"
              />
              {isConnected ? 'Active' : 'Paused'}
            </span>
          </div>

          <div className="text-[11px] text-white/40 font-mono mt-1.5 flex items-center gap-3">
            <span className="flex items-center gap-1">
              <Shield className="w-3 h-3 text-emerald-400/80" aria-hidden="true" />
              PR Automated Gating
            </span>
            {repo.created_at && (
              <>
                <span>•</span>
                <span className="flex items-center gap-1">
                  <Clock className="w-3 h-3 text-white/40" aria-hidden="true" />
                  Connected {new Date(repo.created_at).toLocaleDateString()}
                </span>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="flex items-center gap-2.5 shrink-0 self-end md:self-auto">
        <button
          type="button"
          onClick={onTriggerReview}
          disabled={triggering || !isConnected}
          aria-label={`Trigger review for ${repoName}`}
          className={`inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 text-xs font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer ${focusRing}`}
        >
          {triggering ? (
            <>
              <Loader2 className="w-3.5 h-3.5 animate-spin" aria-hidden="true" />
              <span>Starting…</span>
            </>
          ) : (
            <>
              <Play className="w-3.5 h-3.5 fill-current" aria-hidden="true" />
              <span>Trigger Review</span>
            </>
          )}
        </button>

        <button
          type="button"
          onClick={onDisconnect}
          disabled={disconnecting}
          aria-label={`Disconnect ${repoName}`}
          className={`p-2 rounded-lg bg-white/5 hover:bg-rose-500/10 text-white/50 hover:text-rose-400 border border-white/10 hover:border-rose-500/30 transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer ${focusRing}`}
          title="Disconnect Repository"
        >
          {disconnecting ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin text-rose-400" aria-hidden="true" />
          ) : (
            <Trash2 className="w-3.5 h-3.5" aria-hidden="true" />
          )}
        </button>
      </div>
    </div>
  );
}

function GitHubViewContent({ onSelectReview }: GitHubViewProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const justConnected = searchParams?.get('connected') === '1';

  const [repos, setRepos] = useState<Repository[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [connecting, setConnecting] = useState(false);
  const [triggeringRepoId, setTriggeringRepoId] = useState<string | null>(null);
  const [disconnectingRepoId, setDisconnectingRepoId] = useState<string | null>(null);
  const [successBanner, setSuccessBanner] = useState<string | null>(null);

  // Scope selection state
  const [scopeModalRepo, setScopeModalRepo] = useState<Repository | null>(null);
  const [scopeMode, setScopeMode] = useState<'full_repo' | 'changed_files'>('full_repo');

  const loadRepos = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.listRepositories();
      setRepos(data || []);
    } catch (err: any) {
      setError(err?.message || 'Failed to load repositories');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRepos();
  }, []);

  // Handle post-connect redirect state
  useEffect(() => {
    if (justConnected) {
      setSuccessBanner('GitHub repository successfully connected and configured with default security policies.');
      loadRepos();
      window.history.replaceState({}, '', '/dashboard/github');
    }
  }, [justConnected]);

  const handleConnect = async () => {
    setConnecting(true);
    setError(null);
    try {
      const { install_url } = await api.startGitHubConnect();
      if (install_url) {
        window.location.href = install_url;
      } else {
        throw new Error('No install URL returned by backend.');
      }
    } catch (err: any) {
      setConnecting(false);
      setError(err?.message || 'Failed to start GitHub installation');
    }
  };

  const handleConfirmTriggerReview = async () => {
    if (!scopeModalRepo) return;
    const repoId = scopeModalRepo.repository_id;
    const branch = scopeModalRepo.default_branch || 'main';
    setError(null);
    setTriggeringRepoId(repoId);
    try {
      const response = await api.triggerRepositoryReview(repoId, {
        ref_type: 'branch',
        ref_value: branch,
        scope_mode: scopeMode,
      });

      // The backend returns review_run_id — the run_id that
      // /dashboard/reviews/{run_id} fetches findings for.
      const runId = response.review_run_id;

      if (!runId) {
        setError('Review initiated but no run ID was returned. Check backend logs.');
        return;
      }

      setScopeModalRepo(null);

      if (onSelectReview) {
        onSelectReview(runId);
      } else {
        router.push(`/dashboard/reviews/${runId}`);
      }
    } catch (err: any) {
      setError(err?.message || 'Failed to trigger review');
    } finally {
      setTriggeringRepoId(null);
    }
  };

  const handleDisconnect = async (repoId: string) => {
    if (!window.confirm('Disconnect this repository? Vigil will no longer review pull requests on this repository.')) {
      return;
    }

    setDisconnectingRepoId(repoId);
    setError(null);
    try {
      await api.disconnectRepository(repoId);
      setRepos((prev) => prev.filter((r) => r.repository_id !== repoId));
    } catch (err: any) {
      setError(err?.message || 'Failed to disconnect repository');
    } finally {
      setDisconnectingRepoId(null);
    }
  };

  return (
    <div className="flex-1 overflow-y-auto p-6 flex flex-col gap-6 text-white select-none">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-white/10 pb-5">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
            <Github className="w-5 h-5 text-white/80" aria-hidden="true" />
            <span>GitHub Repositories & CI/CD Integration</span>
          </h1>
          <p className="text-xs text-white/50 mt-1">
            Connect repositories to automate pull request reviews and prevent security regressions.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={loadRepos}
            disabled={loading}
            aria-label="Refresh repositories"
            className={`p-2 rounded-lg bg-white/5 hover:bg-white/10 text-white/70 hover:text-white border border-white/10 transition-colors disabled:opacity-50 cursor-pointer ${focusRing}`}
            title="Refresh"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} aria-hidden="true" />
          </button>

          <button
            type="button"
            onClick={handleConnect}
            disabled={connecting}
            aria-label="Connect GitHub repository"
            className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-slate-950 text-xs font-semibold tracking-wide transition-all shadow-sm cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed ${focusRing}`}
          >
            {connecting ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" aria-hidden="true" />
                <span>Redirecting…</span>
              </>
            ) : (
              <>
                <Plus className="w-3.5 h-3.5" aria-hidden="true" />
                <span>Connect GitHub</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Success Notification Banner */}
      {successBanner && (
        <div
          role="status"
          className="p-4 rounded-xl border border-emerald-500/30 bg-emerald-500/10 text-emerald-300 text-xs flex items-center justify-between gap-3"
        >
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-400" aria-hidden="true" />
            <span>{successBanner}</span>
          </div>
          <button
            type="button"
            onClick={() => setSuccessBanner(null)}
            className="text-emerald-400/60 hover:text-emerald-300 font-mono text-xs px-2 py-0.5 rounded cursor-pointer"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Error Alert */}
      {error && (
        <div
          role="alert"
          className="p-4 rounded-xl border border-rose-500/30 bg-rose-500/10 text-rose-300 text-xs flex items-center justify-between gap-3"
        >
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" aria-hidden="true" />
            <span>{error}</span>
          </div>
          <button
            type="button"
            onClick={loadRepos}
            className={`px-3 py-1 rounded bg-rose-500/20 hover:bg-rose-500/30 text-rose-200 text-xs font-medium cursor-pointer ${focusRing}`}
          >
            Retry
          </button>
        </div>
      )}

      {/* Main Content Area */}
      {loading ? (
        <div className="space-y-3" aria-busy="true" aria-live="polite">
          <div className="text-xs text-white/50 font-mono mb-2 flex items-center gap-2">
            <Loader2 className="w-3.5 h-3.5 animate-spin text-cyan-400" aria-hidden="true" />
            <span>Loading repositories…</span>
          </div>
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="p-5 rounded-xl border border-white/5 bg-white/[0.01] animate-pulse h-24"
            />
          ))}
        </div>
      ) : repos.length === 0 ? (
        <div className="text-center py-16 px-4 rounded-2xl border border-dashed border-white/10 bg-white/[0.01] my-auto flex flex-col items-center">
          <div className="p-4 rounded-2xl bg-white/5 border border-white/10 mb-4 text-white/40">
            <Github className="w-10 h-10" aria-hidden="true" />
          </div>
          <h3 className="text-base font-semibold text-white">No repositories connected yet</h3>
          <p className="mt-2 text-xs text-white/60 max-w-md leading-relaxed">
            Install the Vigil GitHub App on your organization or personal account to select which
            repositories get audited on every pull request.
          </p>
          <button
            type="button"
            onClick={handleConnect}
            disabled={connecting}
            aria-label="Connect GitHub"
            className={`mt-6 inline-flex items-center gap-2 px-6 py-2.5 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-slate-950 text-xs font-semibold tracking-wide transition-all shadow-sm cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed ${focusRing}`}
          >
            {connecting ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" aria-hidden="true" />
                <span>Redirecting to GitHub…</span>
              </>
            ) : (
              <>
                <Plus className="w-3.5 h-3.5" aria-hidden="true" />
                <span>Connect GitHub</span>
              </>
            )}
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="text-xs font-mono text-white/60 uppercase tracking-wider">
              {repos.length} {repos.length === 1 ? 'Repository Connected' : 'Repositories Connected'}
            </div>
            <div className="text-xs font-mono text-emerald-400 flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" aria-hidden="true" />
              <span>CI Automated Triage Ready</span>
            </div>
          </div>

          <div className="grid gap-3">
            {repos.map((repo) => (
              <RepositoryCard
                key={repo.repository_id}
                repo={repo}
                onTriggerReview={() => {
                  setScopeMode('full_repo');
                  setScopeModalRepo(repo);
                }}
                onDisconnect={() => handleDisconnect(repo.repository_id)}
                triggering={triggeringRepoId === repo.repository_id}
                disconnecting={disconnectingRepoId === repo.repository_id}
              />
            ))}
          </div>
        </div>
      )}

      {/* Scope Selection Modal */}
      {scopeModalRepo && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="scope-modal-title"
          className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4"
        >
          <div className="bg-zinc-950 border border-white/15 rounded-2xl p-6 max-w-md w-full shadow-2xl space-y-5 text-white animate-in fade-in zoom-in-95 duration-150">
            <div>
              <div className="flex items-center gap-2 text-cyan-400 text-xs font-mono mb-1">
                <Github className="w-4 h-4" aria-hidden="true" />
                <span>{scopeModalRepo.full_name || scopeModalRepo.repo_name}</span>
              </div>
              <h2 id="scope-modal-title" className="text-lg font-semibold text-white">
                Trigger Security Review
              </h2>
              <p className="text-xs text-white/60 mt-1">
                Select the analysis scope before launching the multi-agent security audit.
              </p>
            </div>

            {/* Radio Options */}
            <div className="space-y-3" role="radiogroup" aria-label="Review Scope Options">
              {/* Option 1: Full Repository (Default) */}
              <label
                onClick={() => setScopeMode('full_repo')}
                className={`p-3.5 rounded-xl border transition-all cursor-pointer flex items-start gap-3 select-none ${
                  scopeMode === 'full_repo'
                    ? 'border-cyan-500/60 bg-cyan-500/10 ring-1 ring-cyan-500/30'
                    : 'border-white/10 bg-white/[0.02] hover:bg-white/[0.05] hover:border-white/20'
                }`}
              >
                <input
                  type="radio"
                  name="scope_mode"
                  value="full_repo"
                  checked={scopeMode === 'full_repo'}
                  onChange={() => setScopeMode('full_repo')}
                  className="mt-1 text-cyan-500 focus:ring-cyan-400 focus:ring-offset-0 bg-transparent border-white/30"
                />
                <div className="flex-1">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-white">Full repository</span>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
                      Default
                    </span>
                  </div>
                  <p className="text-xs text-white/60 mt-0.5">
                    Comprehensive, slower — scans all source files across the repository on branch <code className="font-mono text-cyan-300">{scopeModalRepo.default_branch || 'main'}</code>.
                  </p>
                </div>
              </label>

              {/* Option 2: Changed Files Only */}
              <label
                onClick={() => setScopeMode('changed_files')}
                className={`p-3.5 rounded-xl border transition-all cursor-pointer flex items-start gap-3 select-none ${
                  scopeMode === 'changed_files'
                    ? 'border-cyan-500/60 bg-cyan-500/10 ring-1 ring-cyan-500/30'
                    : 'border-white/10 bg-white/[0.02] hover:bg-white/[0.05] hover:border-white/20'
                }`}
              >
                <input
                  type="radio"
                  name="scope_mode"
                  value="changed_files"
                  checked={scopeMode === 'changed_files'}
                  onChange={() => setScopeMode('changed_files')}
                  className="mt-1 text-cyan-500 focus:ring-cyan-400 focus:ring-offset-0 bg-transparent border-white/30"
                />
                <div className="flex-1">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-white">Changed files only</span>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-white/10 text-white/60 border border-white/10">
                      Fast
                    </span>
                  </div>
                  <p className="text-xs text-white/60 mt-0.5">
                    Fast, small — scans only recently modified diffs and modified files.
                  </p>
                </div>
              </label>
            </div>

            {/* Modal Actions */}
            <div className="flex items-center justify-end gap-3 pt-2 border-t border-white/10">
              <button
                type="button"
                onClick={() => setScopeModalRepo(null)}
                disabled={triggeringRepoId !== null}
                className={`px-4 py-2 rounded-lg text-xs font-medium text-white/70 hover:text-white hover:bg-white/10 transition-colors cursor-pointer disabled:opacity-50 ${focusRing}`}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmTriggerReview}
                disabled={triggeringRepoId !== null}
                className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-slate-950 text-xs font-semibold tracking-wide transition-all shadow-sm cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed ${focusRing}`}
              >
                {triggeringRepoId ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" aria-hidden="true" />
                    <span>Initiating Analysis…</span>
                  </>
                ) : (
                  <>
                    <Play className="w-3.5 h-3.5 fill-current" aria-hidden="true" />
                    <span>Start Review</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export function GitHubView(props: GitHubViewProps) {
  return (
    <Suspense fallback={<div className="p-6 text-xs text-white/50 font-mono">Loading GitHub View…</div>}>
      <GitHubViewContent {...props} />
    </Suspense>
  );
}

export default GitHubView;
