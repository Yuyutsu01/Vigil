import React from 'react';

export const BrandLogos: React.FC = () => {
  // Core Technology & Security Frameworks: React, Alembic, FastAPI, LangGraph, JWT, PostgreSQL, Docker, CWE, Semgrep
  return (
    <div className="relative z-20 py-10 sm:py-12 px-4 w-full border-b border-white/10 bg-black flex items-center justify-center gap-6 sm:gap-10 md:gap-14 flex-wrap opacity-75 hover:opacity-100 transition-opacity select-none">
      {/* 1. React */}
      <div className="flex items-center gap-2 text-white/90 font-medium text-[13.5px] sm:text-[14.5px] tracking-tight group hover:text-white transition-colors">
        <svg className="w-4 h-4 text-white/60 group-hover:rotate-45 transition-transform duration-500 fill-none stroke-current" viewBox="-11.5 -10.23174 23 20.46348">
          <circle cx="0" cy="0" r="2.05" fill="rgba(255,255,255,0.65)" stroke="none" />
          <g stroke="rgba(255,255,255,0.65)" strokeWidth="1" fill="none">
            <ellipse rx="11" ry="4.2" />
            <ellipse rx="11" ry="4.2" transform="rotate(60)" />
            <ellipse rx="11" ry="4.2" transform="rotate(120)" />
          </g>
        </svg>
        <span className="font-semibold">React</span>
      </div>

      {/* 2. Alembic */}
      <div className="flex items-center gap-2 text-white/90 font-medium text-[13.5px] sm:text-[14.5px] tracking-tight group hover:text-white transition-colors">
        <svg className="w-4 h-4 text-amber-400 fill-none stroke-current" viewBox="0 0 24 24" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M10 2v7.31L4.1 19.3A2 2 0 0 0 5.8 22h12.4a2 2 0 0 0 1.7-2.7L14 9.31V2" />
          <path d="M8.5 2h7" />
          <path d="M7 16h10" />
        </svg>
        <span className="font-semibold">Alembic</span>
      </div>

      {/* 3. FastAPI */}
      <div className="flex items-center gap-2 text-white/90 font-medium text-[13.5px] sm:text-[14.5px] tracking-tight group hover:text-white transition-colors">
        <svg className="w-4 h-4 fill-emerald-400" viewBox="0 0 24 24">
          <circle cx="12" cy="12" r="10" fill="#059669" fillOpacity="0.2" stroke="#10b981" strokeWidth="1.5" />
          <path d="M13 3L6 14h5l-2 7 9-12h-5l2-6z" fill="rgba(255,255,255,0.60)" />
        </svg>
        <span className="font-semibold">FastAPI</span>
      </div>

      {/* 4. LangGraph */}
      <div className="flex items-center gap-2 text-white/90 font-medium text-[13.5px] sm:text-[14.5px] tracking-tight group hover:text-white transition-colors">
        <svg className="w-4 h-4 fill-none stroke-purple-400" viewBox="0 0 24 24" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="6" cy="6" r="3" fill="#a855f7" fillOpacity="0.3" />
          <circle cx="18" cy="6" r="3" fill="#a855f7" fillOpacity="0.3" />
          <circle cx="12" cy="18" r="3" fill="#a855f7" fillOpacity="0.3" />
          <path d="M8.5 7.5L15.5 7.5" />
          <path d="M7.5 8.5L10.5 15.5" />
          <path d="M16.5 8.5L13.5 15.5" />
        </svg>
        <span className="font-semibold">LangGraph</span>
      </div>

      {/* 5. JWT */}
      <div className="flex items-center gap-2 text-white/90 font-medium text-[13.5px] sm:text-[14.5px] tracking-tight group hover:text-white transition-colors">
        <svg className="w-4 h-4 fill-none stroke-pink-400" viewBox="0 0 24 24" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
          <path d="M7 11V7a5 5 0 0 1 10 0v4" />
          <circle cx="12" cy="16.5" r="1.5" fill="#ffffff" />
        </svg>
        <span className="font-semibold font-mono">JWT</span>
      </div>

      {/* 6. PostgreSQL */}
      <div className="flex items-center gap-2 text-white/90 font-medium text-[13.5px] sm:text-[14.5px] tracking-tight group hover:text-white transition-colors">
        <svg className="w-4 h-4 text-sky-400 fill-none stroke-current" viewBox="0 0 24 24" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <ellipse cx="12" cy="5" rx="9" ry="3" />
          <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
          <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
        </svg>
        <span className="font-semibold">PostgreSQL</span>
      </div>

      {/* 7. Docker */}
      <div className="flex items-center gap-2 text-white/90 font-medium text-[13.5px] sm:text-[14.5px] tracking-tight group hover:text-white transition-colors">
        <svg className="w-4 h-4 text-blue-400 fill-current" viewBox="0 0 24 24">
          <path d="M13.983 11.078h2.119a.186.186 0 00.186-.185V9.006a.186.186 0 00-.186-.186h-2.119a.185.185 0 00-.185.185v1.888c0 .102.083.185.185.185m-2.954-5.43h2.118a.186.186 0 00.186-.186V3.574a.186.186 0 00-.186-.185h-2.118a.185.185 0 00-.185.185v1.888c0 .102.082.185.185.185m0 2.716h2.118a.187.187 0 00.186-.186V6.29a.186.186 0 00-.186-.185h-2.118a.185.185 0 00-.185.185v1.887c0 .102.082.186.185.186m-2.93 0h2.12a.186.186 0 00.184-.186V6.29a.185.185 0 00-.185-.185H8.1a.185.185 0 00-.185.185v1.887c0 .102.083.186.185.186m-2.964 0h2.119a.186.186 0 00.185-.186V6.29a.185.185 0 00-.185-.185H5.136a.186.186 0 00-.186.185v1.887c0 .102.084.186.186.186m5.893 2.714h2.119a.186.186 0 00.186-.185V9.006a.186.186 0 00-.186-.186h-2.119a.185.185 0 00-.185.185v1.888c0 .102.082.185.185.185m-2.93 0h2.12a.185.185 0 00.184-.185V9.006a.185.185 0 00-.184-.186h-2.12a.185.185 0 00-.184.185v1.888c0 .102.083.185.185.185m-2.964 0h2.119a.185.185 0 00.185-.185V9.006a.185.185 0 00-.185-.186H5.136a.186.186 0 00-.186.185v1.888c0 .102.084.185.186.185m-2.928 0h2.119a.185.185 0 00.185-.185V9.006a.185.185 0 00-.185-.186H2.208a.186.186 0 00-.186.185v1.888c0 .102.084.185.186.185m21.724-.303c-.347-.232-1.397-.306-2.2-.083-.177-.852-.777-1.503-1.637-1.78l-.348-.112-.224.286c-.468.599-.785 1.342-.924 2.164-.53-.186-1.127-.267-1.764-.267H.215a.214.214 0 00-.215.216c0 1.256.242 2.457.7 3.545.922 2.188 2.631 3.824 4.814 4.606a14.246 14.246 0 004.996 1.058c4.27 0 8.083-1.859 10.742-4.831l.243-.271-.345-.119c-.394-.136-.677-.282-.871-.448.868-.088 2.215-.494 2.825-1.725l.18-.363-.353-.176z" />
        </svg>
        <span className="font-semibold">Docker</span>
      </div>

      {/* 8. CWE */}
      <div className="flex items-center gap-2 text-white/90 font-medium text-[13.5px] sm:text-[14.5px] tracking-tight group hover:text-white transition-colors">
        <svg className="w-4 h-4 text-amber-400 fill-none stroke-current" viewBox="0 0 24 24" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
          <path d="M9 12l2 2 4-4" />
        </svg>
        <span className="font-semibold font-mono text-amber-300">CWE</span>
      </div>

      {/* 9. Semgrep */}
      <div className="flex items-center gap-2 text-white/90 font-mono text-[13px] sm:text-[14px] tracking-tight group hover:text-white transition-colors">
        <svg className="w-4 h-4 text-white/60 fill-none stroke-current" viewBox="0 0 24 24" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="4 17 10 11 4 5" />
          <line x1="12" y1="19" x2="20" y2="19" />
        </svg>
        <span className="font-bold text-white/70">Semgrep</span>
      </div>
    </div>
  );
};
