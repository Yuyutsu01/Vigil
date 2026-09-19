'use client';

import React, { useState } from 'react';
import {
  GitCommit,
  Copy,
  Check,
  ExternalLink,
  ShieldCheck,
  CheckCircle2,
  Play,
  GitPullRequest,
  Terminal,
  Loader2,
  X,
  ShieldAlert,
  FileCode2,
} from 'lucide-react';
import { PATCH_PROPOSALS } from '@/data/vigilData';
import { SeverityBadge } from './SeverityBadge';
import { focusRing } from '@/lib/styles';

interface PatchesViewProps {
  onSelectReview: (reviewId: string) => void;
}

interface ValidationModalState {
  isOpen: boolean;
  patchId: string;
  patchTitle: string;
  targetFile: string;
  diffSnippet: string;
  status: 'running' | 'passed' | 'failed';
  logs: string[];
}

interface ApplyModalState {
  isOpen: boolean;
  patchId: string;
  patchTitle: string;
  targetFile: string;
  branchName: string;
  commitMsg: string;
  status: 'idle' | 'applying' | 'applied';
  prUrl: string;
}

export const PatchesView: React.FC<PatchesViewProps> = ({ onSelectReview }) => {
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [validatedPatches, setValidatedPatches] = useState<Record<string, 'passed' | 'failed'>>({
    'patch-cwe-89-order': 'passed',
  });

  const [validationModal, setValidationModal] = useState<ValidationModalState>({
    isOpen: false,
    patchId: '',
    patchTitle: '',
    targetFile: '',
    diffSnippet: '',
    status: 'running',
    logs: [],
  });

  const [applyModal, setApplyModal] = useState<ApplyModalState>({
    isOpen: false,
    patchId: '',
    patchTitle: '',
    targetFile: '',
    branchName: '',
    commitMsg: '',
    status: 'idle',
    prUrl: '',
  });

  const handleCopy = (id: string, patch: string) => {
    navigator.clipboard.writeText(patch);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleRunValidation = (patch: typeof PATCH_PROPOSALS[0]) => {
    setValidationModal({
      isOpen: true,
      patchId: patch.id,
      patchTitle: patch.title,
      targetFile: patch.targetFile,
      diffSnippet: patch.diffSnippet,
      status: 'running',
      logs: [
        `[vigil-sandbox] Initializing isolated AST evaluation sandbox...`,
        `[vigil-sandbox] Target container runtime: gVisor (runsc) / Static AST Sandbox`,
        `[vigil-sandbox] Applying unified patch hunk to ${patch.targetFile}...`,
      ],
    });

    setTimeout(() => {
      setValidationModal((prev) => ({
        ...prev,
        logs: [
          ...prev.logs,
          `[ast-parser] AST validation check: PASSED (Zero syntax errors)`,
          `[taint-tracer] Dataflow containment check: PASSED (Taint sources neutralized)`,
          `[regression-test] Running unit test assertions...`,
        ],
      }));
    }, 600);

    setTimeout(() => {
      setValidationModal((prev) => ({
        ...prev,
        status: 'passed',
        logs: [
          ...prev.logs,
          `[regression-test] ✓ test_sanitized_input_handling (14ms)`,
          `[regression-test] ✓ test_unauthorized_payload_rejection (28ms)`,
          `[regression-test] ✓ test_backward_compatibility_schema (12ms)`,
          `[vigil-sandbox] Validation complete: 3 passed, 0 failed. Verdict: PASSED.`,
        ],
      }));
      setValidatedPatches((prev) => ({ ...prev, [patch.id]: 'passed' }));
    }, 1200);
  };

  const handleOpenApply = (patch: typeof PATCH_PROPOSALS[0]) => {
    const slug = patch.cwe.toLowerCase().replace(/[^a-z0-9]/g, '-');
    setApplyModal({
      isOpen: true,
      patchId: patch.id,
      patchTitle: patch.title,
      targetFile: patch.targetFile,
      branchName: `vigil/fix-${slug}-${patch.targetFile.replace(/[\/\.]/g, '-')}`,
      commitMsg: `fix(${slug}): ${patch.title} [Vigil Autonomous Remediation]`,
      status: 'idle',
      prUrl: '',
    });
  };

  const handleConfirmApply = () => {
    setApplyModal((prev) => ({ ...prev, status: 'applying' }));
    setTimeout(() => {
      const prNumber = Math.floor(Math.random() * 80) + 12;
      setApplyModal((prev) => ({
        ...prev,
        status: 'applied',
        prUrl: `https://github.com/acme-org/repo/pull/${prNumber}`,
      }));
    }, 900);
  };

  return (
    <div className="flex-1 overflow-y-auto p-6 flex flex-col gap-6 text-white select-none">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-white/10 pb-5">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
            <GitCommit className="w-5 h-5 text-white/80" />
            <span>Autonomous Patch Proposals</span>
          </h1>
          <p className="text-xs text-white/50 mt-1">
            Machine-generated remediation diffs verified against AST dataflow constraints.
          </p>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 text-xs font-mono text-emerald-300">
          <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
          <span>Automated Regression Safe</span>
        </div>
      </div>

      {/* Patch List */}
      <div className="flex flex-col gap-5">
        {PATCH_PROPOSALS.map((patch) => {
          const isValidated = validatedPatches[patch.id] === 'passed';
          return (
            <div
              key={patch.id}
              className="rounded-2xl border border-white/15 bg-white/[0.02] p-5 flex flex-col gap-4 transition-all hover:border-white/25"
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-white/10 pb-3">
                <div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-mono text-xs text-white/50">{patch.id}</span>
                    <SeverityBadge severity={patch.severity} size="sm" />
                    <span className="font-mono text-xs text-white/80 bg-white/10 px-2 py-0.5 rounded-full border border-white/10">
                      {patch.cwe}
                    </span>
                    {isValidated ? (
                      <span className="font-mono text-xs text-emerald-300 bg-emerald-500/10 border border-emerald-500/30 px-2 py-0.5 rounded-full flex items-center gap-1">
                        <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                        <span>Sandbox Validated</span>
                      </span>
                    ) : (
                      <span className="font-mono text-xs text-white/50 bg-white/5 border border-white/10 px-2 py-0.5 rounded-full">
                        Syntax Verified
                      </span>
                    )}
                  </div>
                  <h3 className="text-sm font-semibold text-white mt-1.5">{patch.title}</h3>
                  <div className="text-xs text-white/50 font-mono mt-0.5">
                    Target: <span className="text-white/80">{patch.targetFile}</span> (Lines {patch.linesAffected})
                  </div>
                </div>

                <div className="flex items-center gap-2 flex-wrap">
                  {/* Validate in Sandbox Button */}
                  <button
                    onClick={() => handleRunValidation(patch)}
                    className="px-3 py-1.5 rounded-full border border-purple-500/30 bg-purple-500/10 hover:bg-purple-500/20 text-xs text-purple-200 flex items-center gap-1.5 transition-colors cursor-pointer"
                    title="Validate patch AST syntax & run regression checks in isolated sandbox"
                  >
                    <Play className="w-3 h-3 text-purple-400 fill-purple-400" />
                    <span>{isValidated ? 'Re-Validate Sandbox' : 'Validate in Sandbox'}</span>
                  </button>

                  {/* Apply Patch Button */}
                  <button
                    onClick={() => handleOpenApply(patch)}
                    className="px-3 py-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 hover:bg-emerald-500/20 text-xs text-emerald-200 flex items-center gap-1.5 transition-colors cursor-pointer"
                    title="Apply patch to ephemeral Git branch and create draft PR"
                  >
                    <GitPullRequest className="w-3.5 h-3.5 text-emerald-400" />
                    <span>Apply Patch</span>
                  </button>

                  {/* Copy Diff Button */}
                  <button
                    onClick={() => handleCopy(patch.id, patch.diffSnippet)}
                    className="px-3 py-1.5 rounded-full border border-white/15 bg-white/5 hover:bg-white/15 text-xs text-white flex items-center gap-1.5 transition-colors cursor-pointer"
                  >
                    {copiedId === patch.id ? (
                      <>
                        <Check className="w-3.5 h-3.5 text-emerald-400" />
                        <span className="text-emerald-400">Copied</span>
                      </>
                    ) : (
                      <>
                        <Copy className="w-3.5 h-3.5 text-white/60" />
                        <span>Copy Diff</span>
                      </>
                    )}
                  </button>

                  {/* Inspect Review Button */}
                  <button
                    onClick={() => onSelectReview(patch.relatedReviewId)}
                    className="px-3 py-1.5 rounded-full bg-white hover:bg-white/90 text-black text-xs font-semibold flex items-center gap-1.5 transition-colors cursor-pointer"
                  >
                    <span>Inspect Review</span>
                    <ExternalLink className="w-3 h-3" />
                  </button>
                </div>
              </div>

              <p className="text-xs text-white/70 leading-relaxed font-normal">
                {patch.explanation}
              </p>

              {/* Unified Diff Box */}
              <div className="rounded-xl border border-white/10 bg-black overflow-hidden font-mono text-xs select-text">
                <div className="px-3.5 py-1.5 bg-white/[0.04] border-b border-white/10 text-[11px] text-white/50 flex justify-between items-center">
                  <div className="flex items-center gap-1.5">
                    <FileCode2 className="w-3.5 h-3.5 text-white/40" />
                    <span>Unified Diff Patch — {patch.targetFile}</span>
                  </div>
                  <span className="text-emerald-400 font-sans flex items-center gap-1 text-[11px]">
                    <CheckCircle2 className="w-3 h-3 text-emerald-400" /> AST Constraint Safe
                  </span>
                </div>
                <pre className="p-4 text-xs text-white/90 overflow-x-auto whitespace-pre leading-relaxed font-mono">
                  {patch.diffSnippet}
                </pre>
              </div>
            </div>
          );
        })}
      </div>

      {/* Sandbox Validation Live Modal */}
      {validationModal.isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in">
          <div className="w-full max-w-xl rounded-2xl border border-white/20 bg-neutral-950 p-6 shadow-2xl flex flex-col gap-4 text-white">
            <div className="flex items-center justify-between border-b border-white/10 pb-3">
              <div className="flex items-center gap-2">
                <Terminal className="w-5 h-5 text-purple-400" />
                <h2 className="text-base font-semibold text-white">Isolated Sandbox Validation</h2>
              </div>
              <button
                onClick={() => setValidationModal((prev) => ({ ...prev, isOpen: false }))}
                className="p-1 rounded-full hover:bg-white/10 text-white/50 hover:text-white transition-colors cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="flex flex-col gap-1 text-xs">
              <div className="font-semibold text-white/90">{validationModal.patchTitle}</div>
              <div className="text-white/50 font-mono">Target: {validationModal.targetFile}</div>
            </div>

            {/* Validation Terminal Output */}
            <div className="rounded-xl border border-white/15 bg-black p-4 font-mono text-xs text-white/80 flex flex-col gap-1.5 max-h-60 overflow-y-auto">
              {validationModal.logs.map((log, idx) => (
                <div
                  key={idx}
                  className={`${
                    log.includes('PASSED') || log.includes('✓')
                      ? 'text-emerald-400'
                      : log.includes('FAILED')
                      ? 'text-rose-400'
                      : 'text-white/70'
                  }`}
                >
                  {log}
                </div>
              ))}
              {validationModal.status === 'running' && (
                <div className="flex items-center gap-2 text-purple-300 animate-pulse mt-1">
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Executing AST containment & regression assertions...</span>
                </div>
              )}
            </div>

            <div className="flex items-center justify-between pt-2 border-t border-white/10">
              <div className="flex items-center gap-2 text-xs">
                {validationModal.status === 'running' ? (
                  <span className="text-purple-300 font-mono flex items-center gap-1.5">
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    Running in gVisor sandbox...
                  </span>
                ) : (
                  <span className="text-emerald-400 font-mono font-semibold flex items-center gap-1.5">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    Verdict: PASSED (Zero Regression)
                  </span>
                )}
              </div>
              <button
                onClick={() => setValidationModal((prev) => ({ ...prev, isOpen: false }))}
                className={`px-4 py-2 rounded-xl bg-white hover:bg-white/90 text-black text-xs font-semibold cursor-pointer ${focusRing}`}
              >
                Close Logs
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Apply Patch Modal */}
      {applyModal.isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in">
          <div className="w-full max-w-lg rounded-2xl border border-white/20 bg-neutral-950 p-6 shadow-2xl flex flex-col gap-4 text-white">
            <div className="flex items-center justify-between border-b border-white/10 pb-3">
              <div className="flex items-center gap-2">
                <GitPullRequest className="w-5 h-5 text-emerald-400" />
                <h2 className="text-base font-semibold text-white">Apply Autonomous Remediation</h2>
              </div>
              <button
                onClick={() => setApplyModal((prev) => ({ ...prev, isOpen: false }))}
                className="p-1 rounded-full hover:bg-white/10 text-white/50 hover:text-white transition-colors cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {applyModal.status === 'applied' ? (
              <div className="flex flex-col gap-4 py-2">
                <div className="p-4 rounded-xl border border-emerald-500/30 bg-emerald-500/10 flex flex-col gap-2">
                  <div className="flex items-center gap-2 text-emerald-300 font-semibold text-sm">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    <span>Patch Branch Created & PR Opened</span>
                  </div>
                  <p className="text-xs text-white/70">
                    The remediation diff was committed to branch <code className="text-emerald-300 font-mono">{applyModal.branchName}</code>.
                  </p>
                </div>
                <div className="flex justify-end gap-2">
                  <button
                    onClick={() => setApplyModal((prev) => ({ ...prev, isOpen: false }))}
                    className={`px-4 py-2 rounded-xl bg-white text-black font-semibold text-xs cursor-pointer ${focusRing}`}
                  >
                    Done
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex flex-col gap-4">
                <p className="text-xs text-white/70">
                  Apply <strong className="text-white">{applyModal.patchTitle}</strong> to your repository on an isolated remediation branch.
                </p>

                <div className="flex flex-col gap-1.5 text-xs">
                  <label className="text-white/60 font-mono">Target Remediation Branch</label>
                  <input
                    type="text"
                    value={applyModal.branchName}
                    onChange={(e) => setApplyModal((prev) => ({ ...prev, branchName: e.target.value }))}
                    className="w-full px-3 py-2 rounded-xl bg-white/5 border border-white/15 text-xs font-mono text-white focus:outline-none focus:border-emerald-500"
                  />
                </div>

                <div className="flex flex-col gap-1.5 text-xs">
                  <label className="text-white/60 font-mono">Commit Message</label>
                  <input
                    type="text"
                    value={applyModal.commitMsg}
                    onChange={(e) => setApplyModal((prev) => ({ ...prev, commitMsg: e.target.value }))}
                    className="w-full px-3 py-2 rounded-xl bg-white/5 border border-white/15 text-xs text-white focus:outline-none focus:border-emerald-500"
                  />
                </div>

                <div className="flex items-center justify-end gap-2 pt-2 border-t border-white/10">
                  <button
                    onClick={() => setApplyModal((prev) => ({ ...prev, isOpen: false }))}
                    className="px-4 py-2 rounded-xl border border-white/15 text-xs text-white/70 hover:text-white cursor-pointer"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleConfirmApply}
                    disabled={applyModal.status === 'applying'}
                    className={`px-4 py-2 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-black font-semibold text-xs flex items-center gap-1.5 cursor-pointer ${focusRing}`}
                  >
                    {applyModal.status === 'applying' ? (
                      <>
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        <span>Applying Patch...</span>
                      </>
                    ) : (
                      <>
                        <GitPullRequest className="w-3.5 h-3.5" />
                        <span>Create Remediated PR</span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
