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
  ChevronLeft,
  ChevronRight,
  Shield,
  X,
} from 'lucide-react';
import { VigilNavSection } from '@/lib/types';
import { focusRing } from '@/lib/styles';

interface SidebarProps {
  currentSection: VigilNavSection;
  onNavigate: (section: VigilNavSection) => void;
  onNewReview: () => void;
  reviewCount: number;
  collapsed?: boolean;
  onToggleCollapse?: () => void;
  isMobileDrawer?: boolean;
  onCloseMobileDrawer?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentSection,
  onNavigate,
  onNewReview,
  reviewCount,
  collapsed = false,
  onToggleCollapse,
  isMobileDrawer = false,
  onCloseMobileDrawer,
}) => {
  const navItems: {
    section: VigilNavSection;
    label: string;
    icon: React.ComponentType<{ className?: string }>;
    badge?: number | string;
  }[] = [
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
    <aside
      className={`${
        isMobileDrawer
          ? 'w-64 h-full'
          : collapsed
          ? 'w-16'
          : 'w-64'
      } bg-[#070709] border-r border-white/10 flex flex-col justify-between shrink-0 select-none text-white transition-all duration-200 ease-in-out`}
    >
      <div className={`p-3 sm:p-4 flex flex-col ${collapsed ? 'gap-3 items-center' : 'gap-5'}`}>
        {/* Header Branding */}
        <div
          className={`flex items-center ${
            collapsed ? 'justify-center' : 'justify-between'
          } pb-2 border-b border-white/10 w-full`}
        >
          <div className="flex items-center gap-2.5">
            <img
              src="/images/vigil-logo.png"
              alt="Vigil"
              className="w-7 h-auto shrink-0 drop-shadow-[0_0_8px_rgba(255,255,255,0.2)]"
            />
            {!collapsed && (
              <div>
                <div className="font-bold tracking-widest text-xs uppercase text-white truncate">
                  VIGIL CONSOLE
                </div>

              </div>
            )}
          </div>

          {isMobileDrawer ? (
            <button
              type="button"
              onClick={onCloseMobileDrawer}
              aria-label="Close navigation menu"
              className={`p-1 rounded-lg text-white/60 hover:text-white hover:bg-white/10 ${focusRing}`}
            >
              <X className="w-4 h-4" />
            </button>
          ) : !collapsed ? (
            <span className="w-2 h-2 rounded-full bg-white/30 animate-pulse" />
          ) : null}
        </div>

        {/* New Review Button */}
        <button
          type="button"
          onClick={onNewReview}
          title="New Review Run"
          aria-label="New Review Run"
          className={`${
            collapsed
              ? 'w-9 h-9 p-0 justify-center'
              : 'w-full py-2 px-3 justify-center'
          } bg-white hover:bg-white/90 text-black rounded-xl text-xs font-semibold flex items-center gap-2 transition-colors cursor-pointer shadow-sm ${focusRing}`}
        >
          <Plus className="w-3.5 h-3.5 stroke-[2.5] shrink-0" />
          {!collapsed && <span>New Review Run</span>}
        </button>

        {/* Navigation Items */}
        <nav
          className="flex flex-col gap-1 text-xs w-full"
          aria-label="Main Navigation"
        >
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = currentSection === item.section;
            return (
              <button
                key={item.section}
                type="button"
                onClick={() => onNavigate(item.section)}
                title={item.label}
                aria-label={collapsed ? `Go to ${item.label}` : item.label}
                className={`${
                  collapsed ? 'justify-center px-2 py-2.5' : 'justify-between px-3 py-2'
                } w-full flex items-center rounded-xl text-left transition-all cursor-pointer ${focusRing} ${
                  isActive
                    ? 'bg-white/10 text-white font-semibold border border-white/15'
                    : 'text-white/60 hover:text-white hover:bg-white/[0.04]'
                }`}
              >
                <div className={`flex items-center ${collapsed ? 'justify-center' : 'gap-2.5'}`}>
                  <Icon
                    className={`w-4 h-4 shrink-0 ${
                      isActive ? 'text-white' : 'text-white/50'
                    }`}
                  />
                  {!collapsed && <span className="truncate">{item.label}</span>}
                </div>
                {!collapsed && item.badge !== undefined && (
                  <span
                    className={`text-[10px] font-mono px-2 py-0.2 rounded-full shrink-0 ${
                      isActive
                        ? 'bg-white text-black font-bold'
                        : 'bg-white/10 text-white/70'
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

      {/* Footer Controls & Telemetry */}
      <div className={`p-3 sm:p-4 border-t border-white/10 flex flex-col ${collapsed ? 'gap-2 items-center' : 'gap-3'}`}>


        {/* Tenant Info */}
        {collapsed ? (
          <div
            className="w-8 h-8 rounded-lg bg-white/5 border border-white/10 flex items-center justify-center text-white/60 text-[10px] font-mono"
            title="Tenant: acme-corp (SOC2-Compliant)"
          >
            <Shield className="w-3.5 h-3.5 text-white/60" />
          </div>
        ) : (
          <div className="text-[10.5px] text-white/40 flex justify-between items-center w-full">
            <span className="truncate">Tenant: acme-corp</span>
            <span className="text-white/30 font-mono shrink-0">SOC2</span>
          </div>
        )}

        {/* Collapse / Expand Toggle Button */}
        {onToggleCollapse && !isMobileDrawer && (
          <button
            type="button"
            onClick={onToggleCollapse}
            aria-label="Toggle sidebar"
            aria-expanded={!collapsed}
            title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            className={`w-full py-1.5 rounded-lg border border-white/10 bg-white/[0.03] hover:bg-white/10 text-white/60 hover:text-white flex items-center justify-center transition-colors cursor-pointer ${focusRing}`}
          >
            {collapsed ? (
              <ChevronRight className="w-4 h-4" />
            ) : (
              <div className="flex items-center gap-1.5 text-xs">
                <ChevronLeft className="w-4 h-4" />
                <span>Collapse</span>
              </div>
            )}
          </button>
        )}
      </div>
    </aside>
  );
};
