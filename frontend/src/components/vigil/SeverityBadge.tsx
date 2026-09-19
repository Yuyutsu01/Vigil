'use client';

import React from 'react';
import { AlertOctagon, AlertTriangle, AlertCircle, Info } from 'lucide-react';
import { Severity } from '@/lib/types';

interface SeverityBadgeProps {
  severity: Severity;
  size?: 'sm' | 'md';
}

export const SeverityBadge: React.FC<SeverityBadgeProps> = ({ severity, size = 'md' }) => {
  const config = {
    critical: {
      label: 'Critical',
      icon: AlertOctagon,
      bg: 'bg-red-500/15 border-red-500/30 text-red-400',
    },
    high: {
      label: 'High',
      icon: AlertTriangle,
      bg: 'bg-orange-500/15 border-orange-500/30 text-orange-400',
    },
    medium: {
      label: 'Medium',
      icon: AlertCircle,
      bg: 'bg-amber-500/15 border-amber-500/30 text-amber-400',
    },
    low: {
      label: 'Low',
      icon: Info,
      bg: 'bg-blue-500/15 border-blue-500/30 text-blue-400',
    },
    info: {
      label: 'Info',
      icon: Info,
      bg: 'bg-white/10 border-white/20 text-white/80',
    },
  }[severity] || {
    label: severity,
    icon: Info,
    bg: 'bg-white/10 border-white/20 text-white/80',
  };

  const Icon = config.icon;
  const sizeClasses =
    size === 'sm' ? 'px-2 py-0.5 text-[11px] gap-1' : 'px-2.5 py-1 text-xs gap-1.5 font-medium';
  const iconSize = size === 'sm' ? 'w-3 h-3' : 'w-3.5 h-3.5';

  return (
    <span
      className={`inline-flex items-center rounded-full border ${config.bg} ${sizeClasses} select-none font-mono tracking-wide`}
    >
      <Icon className={`${iconSize} shrink-0`} />
      <span>{config.label}</span>
    </span>
  );
};
