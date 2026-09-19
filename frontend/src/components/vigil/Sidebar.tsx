'use client';

import React from 'react';
import {
  LayoutDashboard,
  FileCode,
  FileCheck2,
  GitPullRequest,
  GitCommit,
  Bot,
  Target,
  Settings,
  Plus,
} from 'lucide-react';
import { VigilNavSection } from '@/lib/types';

import { focusRing } from '@/lib/styles';

interface SidebarProps {
  currentSection: VigilNavSection;
  onNavigate: (section: VigilNavSection) => void;
  onNewReview: () => void;
  reviewCount: number;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentSection,
  onNavigate,
  onNewReview,
  reviewCount,
}) => {
  const navItems: { section: VigilNavSection; label: string; icon: React.ComponentType<{ className?: string }>; badge?: number | string }[] = [
    { section: 'dashboard', label: 'Overview', icon: LayoutDashboard },
    { section: 'reviews', label: 'All Reviews', icon: FileCode, badge: reviewCount },
    { section: 'github', label: 'GitHub PRs', icon: GitPullRequest, badge: 'CI' },
    { section: 'patches', label: 'Autonomous Patches', icon: GitCommit, badge: 3 },
    { section: 'compliance', label: 'Compliance Dossiers', icon: FileCheck2 },
    { section: 'evaluation', label: 'Benchmark Bench', icon: Target },
    { section: 'agents', label: 'Agent Fleet', icon: Bot },
    { section: 'settings', label: 'Settings', icon: Settings },
  ];

  return (
    <aside className="w-64 bg-[#070709] border-r border-white/10 flex flex-col justify-between shrink-0 select-none text-white">
      <div className="p-4 flex flex-col gap-5">
        <div className="flex items-center justify-between pb-2 border-b border-white/10">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-white flex items-center justify-center text-black font-bold text-xs shadow-[0_0_12px_rgba(255,255,255,0.3)]">
              V
            </div>
            <div>
              <div className="font-bold tracking-widest text-xs uppercase text-white">
                VIGIL CONSOLE
              </div>
              <div className="text-[10px] text-white/40 font-mono">SecOps v2.4.0</div>
            </div>
          </div>
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
        </div>

        <button
          onClick={onNewReview}
          className={`w-full py-2 px-3 bg-white hover:bg-white/90 text-black rounded-xl text-xs font-semibold flex items-center justify-center gap-2 transition-colors cursor-pointer shadow-sm ${focusRing}`}
        >
          <Plus className="w-3.5 h-3.5 stroke-[2.5]" />
          <span>New Review Run</span>
        </button>

        <nav className="flex flex-col gap-1 text-xs" aria-label="Main Navigation">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = currentSection === item.section;
            return (
              <button
                key={item.section}
                onClick={() => onNavigate(item.section)}
                className={`w-full flex items-center justify-between px-3 py-2 rounded-xl text-left transition-all cursor-pointer ${focusRing} ${
                  isActive
                    ? 'bg-white/10 text-white font-semibold border border-white/15'
                    : 'text-white/60 hover:text-white hover:bg-white/[0.04]'
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <Icon className={`w-4 h-4 ${isActive ? 'text-white' : 'text-white/50'}`} />
                  <span>{item.label}</span>
                </div>
                {item.badge !== undefined && (
                  <span
                    className={`text-[10px] font-mono px-2 py-0.2 rounded-full ${
                      isActive ? 'bg-white text-black font-bold' : 'bg-white/10 text-white/70'
                    }`}
                  >
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </nav>
      </div>

      <div className="p-4 border-t border-white/10 flex flex-col gap-3">
        <div className="p-3 rounded-xl border border-white/10 bg-white/[0.02] flex flex-col gap-1.5 text-[11px] font-mono">
          <div className="flex justify-between text-white/50">
            <span>Deterministic Taint</span>
            <span className="text-emerald-400">ACTIVE</span>
          </div>
          <div className="flex justify-between text-white/50">
            <span>Zero-Execution Box</span>
            <span className="text-emerald-400">ENFORCED</span>
          </div>
        </div>

        <div className="text-[10.5px] text-white/40 flex justify-between items-center">
          <span>Tenant: acme-corp</span>
          <span className="text-white/30 font-mono">SOC2-Compliant</span>
        </div>
      </div>
    </aside>
  );
};
