'use client';

import React from 'react';
import { Shield, Wrench, Sparkles } from 'lucide-react';
import { FindingSource } from '@/lib/types';

interface SourceBadgeProps {
  source: FindingSource;
  toolName?: string;
  size?: 'sm' | 'md';
}

export const SourceBadge: React.FC<SourceBadgeProps> = ({ source, toolName, size = 'md' }) => {
  const config = {
    rule: {
      label: 'Rule',
      icon: Shield,
      bg: 'bg-emerald-500/10 border-emerald-500/25 text-emerald-400',
    },
    tool: {
      label: toolName || 'Tool',
      icon: Wrench,
      bg: 'bg-white/10 border-white/20 text-white',
    },
    agent: {
      label: 'Autonomous Agent',
      icon: Sparkles,
      bg: 'bg-cyan-500/10 border-cyan-500/25 text-cyan-400',
    },
    llm: {
      label: 'LLM Reasoner',
      icon: Sparkles,
      bg: 'bg-white/10 border-white/20 text-white',
    },
  }[source] || {
    label: source,
    icon: Shield,
    bg: 'bg-white/10 border-white/20 text-white/80',
  };

  const Icon = config.icon;
  const sizeClasses =
    size === 'sm' ? 'px-2 py-0.5 text-[10.5px] gap-1' : 'px-2.5 py-1 text-xs gap-1.5 font-normal';
  const iconSize = size === 'sm' ? 'w-3 h-3' : 'w-3.5 h-3.5';

  return (
    <span
      className={`inline-flex items-center rounded-full border ${config.bg} ${sizeClasses} select-none font-mono tracking-tight`}
      title={`Finding provenance: ${config.label}`}
    >
      <Icon className={`${iconSize} shrink-0`} />
      <span className="truncate max-w-[130px]">{config.label}</span>
    </span>
  );
};
