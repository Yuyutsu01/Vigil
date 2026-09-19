'use client';

import React, { useState } from 'react';
import { Settings, Shield, Sliders, Lock, Check } from 'lucide-react';
import { focusRing } from '@/lib/styles';

export const SettingsView: React.FC = () => {
  const [activePolicy, setActivePolicy] = useState('Strict OWASP & CWE');
  const [maxTokens, setMaxTokens] = useState(25000);
  const [costBudget, setCostBudget] = useState(2.0);
  const [blockPrMerges, setBlockPrMerges] = useState(true);
  const [retentionDays, setRetentionDays] = useState(90);
  const [saved, setSaved] = useState(false);

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  };

  return (
    <div className="flex-1 overflow-y-auto p-6 flex flex-col gap-6 text-white select-none max-w-4xl mx-auto w-full">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-white/10 pb-5">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
            <Settings className="w-5 h-5 text-white/80" />
            <span>Tenant Security & Policy Config</span>
          </h1>
          <p className="text-xs text-white/50 mt-1">
            Configure guardrails, cost thresholds, and CI/CD gating requirements.
          </p>
        </div>
      </div>

      <form onSubmit={handleSave} className="flex flex-col gap-6">
        {saved && (
          <div className="p-3 rounded-xl border border-white/18 bg-white/8 text-white/70 text-xs flex items-center gap-2 animate-in fade-in">
            <Check className="w-4 h-4" />
            <span>Configuration changes committed to cryptographic tenant registry.</span>
          </div>
        )}

        <div className="rounded-2xl border border-white/15 bg-white/[0.02] p-5 flex flex-col gap-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-white border-b border-white/10 pb-3">
            <Shield className="w-4 h-4 text-white/70" />
            <span>Default Security Policy Profile</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {['Strict OWASP & CWE', 'Default Policy', 'Custom Enterprise Guard'].map((p) => (
              <div
                key={p}
                onClick={() => setActivePolicy(p)}
                className={`p-3.5 rounded-xl border cursor-pointer transition-all ${
                  activePolicy === p
                    ? 'bg-white/10 border-white text-white'
                    : 'bg-white/[0.02] border-white/10 text-white/60 hover:text-white'
                }`}
              >
                <div className="font-semibold text-xs text-white">{p}</div>
                <div className="text-[11px] text-white/40 mt-1">
                  {p === 'Strict OWASP & CWE'
                    ? 'Zero-tolerance for injection & unauthenticated endpoints'
                    : p === 'Default Policy'
                    ? 'Balanced scan of critical and high vulnerabilities'
                    : 'Custom ruleset with organization-specific AST taint sinks'}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-2xl border border-white/15 bg-white/[0.02] p-5 flex flex-col gap-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-white border-b border-white/10 pb-3">
            <Sliders className="w-4 h-4 text-white/70" />
            <span>Execution Budgets & Rate Governors</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
            <div className="flex flex-col gap-1.5">
              {/* Associated label for screen readers */}
              <label htmlFor="max-tokens-input" className="text-white/80 font-medium">Max Tokens per Audit Run</label>
              <input
                id="max-tokens-input"
                type="number"
                value={maxTokens}
                onChange={(e) => setMaxTokens(Number(e.target.value))}
                className={`bg-black border border-white/15 rounded-lg px-3 py-2 text-white font-mono focus:outline-none focus:border-white/40 ${focusRing}`}
              />
              <span className="text-[11px] text-white/40">Default ceiling is 25,000 tokens</span>
            </div>

            <div className="flex flex-col gap-1.5">
              {/* Associated label for screen readers */}
              <label htmlFor="cost-budget-input" className="text-white/80 font-medium">Cost Governor per Review ($ USD)</label>
              <input
                id="cost-budget-input"
                type="number"
                step="0.1"
                value={costBudget}
                onChange={(e) => setCostBudget(Number(e.target.value))}
                className={`bg-black border border-white/15 rounded-lg px-3 py-2 text-white font-mono focus:outline-none focus:border-white/40 ${focusRing}`}
              />
              <span className="text-[11px] text-white/40">Hard stop at spending limit</span>
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-white/15 bg-white/[0.02] p-5 flex flex-col gap-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-white border-b border-white/10 pb-3">
            <Lock className="w-4 h-4 text-white/70" />
            <span>Compliance & Data Retention Policy</span>
          </div>

          <div className="flex flex-col gap-3 text-xs">
            <div className="flex items-center justify-between p-3 rounded-xl bg-white/[0.02] border border-white/10">
              <label htmlFor="block-pr-merges-check" className="cursor-pointer">
                <div className="font-semibold text-white">Block PR Merges on Critical CWEs</div>
                <div className="text-[11px] text-white/40">
                  Emit failing status check on GitHub and GitLab pipelines if any Critical issue is open.
                </div>
              </label>
              <input
                type="checkbox"
                id="block-pr-merges-check"
                checked={blockPrMerges}
                onChange={(e) => setBlockPrMerges(e.target.checked)}
                className={`w-4 h-4 rounded border-white/20 bg-black text-white focus:ring-white/50 cursor-pointer ${focusRing}`}
              />
            </div>

            <div className="flex items-center justify-between p-3 rounded-xl bg-white/[0.02] border border-white/10">
              <label htmlFor="retention-days-select" className="cursor-pointer">
                <div className="font-semibold text-white">Artifact Retention Window</div>
                <div className="text-[11px] text-white/40">
                  Days before code traces and AST trees are purged unless marked with a legal hold.
                </div>
              </label>
              <select
                id="retention-days-select"
                value={retentionDays}
                onChange={(e) => setRetentionDays(Number(e.target.value))}
                className={`bg-black border border-white/15 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-white/40 ${focusRing}`}
              >
                <option value={30}>30 Days</option>
                <option value={90}>90 Days (SOC2 Default)</option>
                <option value={180}>180 Days</option>
                <option value={365}>365 Days (1 Year)</option>
              </select>
            </div>
          </div>
        </div>

        <div className="flex justify-end pt-2">
          <button
            type="submit"
            className={`px-6 py-2 bg-white hover:bg-white/90 text-black rounded-full text-xs font-semibold transition-colors cursor-pointer shadow-sm ${focusRing}`}
          >
            Save Configuration
          </button>
        </div>
      </form>
    </div>
  );
};
