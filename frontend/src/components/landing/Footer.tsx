'use client';

import React from 'react';

interface FooterProps {
  onLinkClick?: (item: string) => void;
  onRequestDemo?: () => void;
  onGetStarted?: () => void;
}

export const Footer: React.FC<FooterProps> = ({ onLinkClick }) => {
  const handleNav = (id: string, e: React.MouseEvent) => {
    e.preventDefault();
    if (onLinkClick) {
      onLinkClick(id);
    } else {
      const el = document.getElementById(id);
      if (el) el.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <footer className="relative z-20 w-full bg-black text-white border-t border-white/10 pt-16 pb-12 px-6 sm:px-10 md:px-16 select-none">
      {/* Selector 10: div:nth-of-type(1) - Upper 4-Column Directory */}
      <div className="max-w-7xl mx-auto grid grid-cols-1 md:grid-cols-4 gap-10 pb-16 border-b border-white/10">
        <div>
          <div className="flex items-center gap-2 mb-4">
            <span className="font-bold text-white text-base tracking-wider">▲ VIGIL</span>
          </div>
          <p className="text-sm text-white/70 leading-relaxed max-w-xs">
            Automated code review assistant that finds bugs and security issues, explains them in plain language, and validates fixes safely.
          </p>
        </div>
        <div>
          <div className="text-xs font-mono uppercase tracking-wider text-white mb-4">Product</div>
          <ul className="space-y-2.5 text-sm text-white/60">
            <li>
              <a
                href="#about"
                onClick={(e) => handleNav('about', e)}
                className="hover:text-white transition-colors cursor-pointer"
              >
                About
              </a>
            </li>
            <li>
              <a
                href="#features"
                onClick={(e) => handleNav('features', e)}
                className="hover:text-white transition-colors cursor-pointer"
              >
                Capabilities
              </a>
            </li>
            <li>
              <a
                href="#benchmarks"
                onClick={(e) => handleNav('benchmarks', e)}
                className="hover:text-white transition-colors cursor-pointer"
              >
                Results
              </a>
            </li>
            <li>
              <a
                href="#execution"
                onClick={(e) => handleNav('execution', e)}
                className="hover:text-white transition-colors cursor-pointer"
              >
                Pipeline
              </a>
            </li>
            <li>
              <a
                href="#verification"
                onClick={(e) => handleNav('verification', e)}
                className="hover:text-white transition-colors cursor-pointer"
              >
                Security
              </a>
            </li>
          </ul>
        </div>
        <div>
          <div className="text-xs font-mono uppercase tracking-wider text-white mb-4">Compliance</div>
          <ul className="space-y-2.5 text-sm text-white/60">
            <li><span className="hover:text-white cursor-pointer">SARIF Exports</span></li>
            <li><span className="hover:text-white cursor-pointer">SOC 2 Type II</span></li>
            <li><span className="hover:text-white cursor-pointer">ISO 27001 Certified</span></li>
            <li><span className="hover:text-white cursor-pointer">NIST CSF 2.0 Mapping</span></li>
          </ul>
        </div>
        <div>
          <div className="text-xs font-mono uppercase tracking-wider text-white mb-4">Security Lead</div>
          <div className="p-4 rounded-xl border border-white/10 bg-white/[0.02] text-sm text-white/70">
            <div className="text-white font-medium mb-1">Zero Data Retention</div>
            Your code is analyzed in isolated memory and never used for model training.
          </div>
        </div>
      </div>

      {/* Selector 9: div:nth-of-type(2) - Bottom Copyright & Legal Row */}
      <div className="max-w-7xl mx-auto pt-8 flex flex-col sm:flex-row items-center justify-between text-xs sm:text-sm text-white/50 gap-4">
        <div>
          &copy; 2026 Vigil. All rights reserved.
        </div>
        <div className="flex items-center gap-6 text-xs sm:text-sm text-white/50">
          <span className="hover:text-white cursor-pointer">Privacy Policy</span>
          <span className="hover:text-white cursor-pointer">Terms of Service</span>
          <span className="hover:text-white cursor-pointer">Security Overview</span>
        </div>
      </div>
    </footer>
  );
};
