'use client';

import React from 'react';
import Link from 'next/link';
import { ArrowLeft, Bell } from 'lucide-react';

import { focusRing } from '@/lib/styles';

interface TopbarProps {
  onBackToMarketing?: () => void;
  title?: string;
}

export const Topbar: React.FC<TopbarProps> = ({ onBackToMarketing, title }) => {
  return (
    <header className="h-14 bg-black border-b border-white/10 px-6 flex items-center justify-between shrink-0 select-none text-white">
      <div className="flex items-center gap-4">
        {onBackToMarketing ? (
          <button
            onClick={onBackToMarketing}
            className={`flex items-center gap-1.5 text-xs text-white/50 hover:text-white transition-colors cursor-pointer py-1 px-2 rounded-full hover:bg-white/5 ${focusRing}`}
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Marketing Site</span>
          </button>
        ) : (
          <Link
            href="/"
            className={`flex items-center gap-1.5 text-xs text-white/50 hover:text-white transition-colors cursor-pointer py-1 px-2 rounded-full hover:bg-white/5 ${focusRing}`}
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Marketing Site</span>
          </Link>
        )}
        {title && (
          <div className="text-xs font-semibold text-white/80 font-mono pl-2 border-l border-white/10">
            {title}
          </div>
        )}
      </div>

      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1.5 text-xs font-mono px-3 py-1 rounded-full border border-white/10 bg-white/[0.02] text-white/70">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
          <span>AST Engines Healthy</span>
        </div>

        <button
          aria-label="Audit notifications"
          className={`p-1.5 rounded-full text-white/50 hover:text-white hover:bg-white/10 transition-colors relative cursor-pointer ${focusRing}`}
          title="Audit notifications"
        >
          <Bell className="w-4 h-4" />
          <span className="absolute top-1 right-1 w-2 h-2 rounded-full bg-white" />
        </button>

        <div className="w-7 h-7 rounded-full bg-white/10 border border-white/20 flex items-center justify-center text-xs font-mono text-white">
          SC
        </div>
      </div>
    </header>
  );
};
