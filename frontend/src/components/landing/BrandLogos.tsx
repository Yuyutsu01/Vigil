import React from 'react';
import { Shield, GitBranch, Terminal } from 'lucide-react';

export const BrandLogos: React.FC = () => {
  // Brand integration logos displayed between the Hero and Content sections
  return (
    <div className="relative z-20 py-10 sm:py-12 px-4 w-full border-b border-white/10 bg-black flex items-center justify-center gap-6 sm:gap-10 md:gap-14 flex-wrap opacity-70 hover:opacity-95 transition-opacity select-none">
      {/* GitHub */}
      <div className="flex items-center gap-1.5 text-white/90 font-medium text-[14px] sm:text-[15px] tracking-tight">
        <svg className="w-4 h-4 fill-current text-white" viewBox="0 0 24 24">
          <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z" />
        </svg>
        <span className="font-semibold">GitHub Actions</span>
      </div>
      {/* GitLab */}
      <div className="flex items-center gap-1.5 text-white/90 font-medium text-[13.5px] sm:text-[14.5px] tracking-tight">
        <GitBranch className="w-3.5 h-3.5 text-orange-400" />
        <span className="font-semibold text-white">GitLab CI</span>
      </div>
      {/* Semgrep AST */}
      <div className="flex items-center gap-1.5 text-white/90 font-mono text-[13px] sm:text-[14px] tracking-tight">
        <Terminal className="w-3.5 h-3.5 text-emerald-400" />
        <span className="font-bold">Semgrep AST</span>
      </div>
      {/* Snyk Security */}
      <div className="flex items-center gap-1.5 text-white/90 font-bold text-[14px] sm:text-[15px] tracking-tight">
        <Shield className="w-3.5 h-3.5 text-purple-400" />
        <span>Snyk CVE</span>
      </div>
      {/* AWS Cloud */}
      <div className="flex items-center gap-1.5 text-white/80 font-medium text-[13.5px] sm:text-[14.5px] tracking-tight">
        <span className="font-semibold text-white">aws</span>
        <span className="text-white/40">|</span>
        <span className="text-white/90">GovCloud</span>
      </div>
      {/* Vercel */}
      <div className="flex items-center gap-1.5 text-white/90 font-medium text-[14px] sm:text-[15px] tracking-tight">
        <svg className="w-3.5 h-3.5 fill-current text-white" viewBox="0 0 76 65" fill="none">
          <path d="M37.5274 0L75.0548 65H0L37.5274 0Z" />
        </svg>
        <span className="font-semibold">Vercel</span>
      </div>
      {/* Supabase */}
      <div className="flex items-center gap-1.5 text-white/90 font-medium text-[14px] sm:text-[15px] tracking-tight">
        <svg className="w-3.5 h-3.5 fill-current text-white" viewBox="0 0 24 24">
          <path d="M21.362 9.354H12V.396a.396.396 0 0 0-.716-.233L.64 14.646a.396.396 0 0 0 .316.635H12v8.958a.396.396 0 0 0 .716.233l10.644-14.483a.396.396 0 0 0-.316-.635z" />
        </svg>
        <span>Supabase</span>
      </div>
    </div>
  );
};
