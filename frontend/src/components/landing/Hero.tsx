'use client';

import React, { useEffect, useState, useRef } from 'react';
import dynamic from 'next/dynamic';

// Dynamically import Three.js / WebGL particle vortex to prevent SSR canvas errors
const Vortex = dynamic(() => import('./Vortex'), {
  ssr: false,
  loading: () => <div className="w-full h-full bg-black" />,
});

// Inline double arrow icon for primary action buttons
function Arrow() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      className="ml-1 inline-block align-[-2px]"
      strokeWidth="1.8"
      stroke="currentColor"
      aria-hidden="true"
    >
      <path
        d="M12.5 18C12.5 18 18.5 13.5811 18.5 12C18.5 10.4188 12.5 6 12.5 6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M5.50005 18C5.50005 18 11.5 13.5811 11.5 12C11.5 10.4188 5.5 6 5.5 6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

// Glowing border star button moving a radial highlight along an SVG offset-path
function StarButton({ onClick }: { onClick?: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        '--duration': 3,
        '--light-width': '110px',
        '--light-color': '#FAFAFA',
        '--border-width': '2px',
        isolation: 'isolate',
        '--path': "path('M 0 0 H 153 V 40 H 0 V 0')",
      } as React.CSSProperties}
      className="group/star-button relative z-[3] inline-flex h-10 items-center justify-center gap-2 overflow-hidden whitespace-nowrap rounded-full border border-slate-200/50 px-5 py-2 text-sm font-medium transition-colors cursor-pointer hover:border-white disabled:pointer-events-none disabled:opacity-50"
    >
      <div
        className="animate-star-btn absolute inset-0 aspect-square bg-[radial-gradient(ellipse_closest-side_at_center,var(--light-color),transparent,transparent)]"
        style={{
          offsetPath: 'var(--path)',
          offsetDistance: '0%',
          width: 'var(--light-width)',
        }}
      />
      <div
        className="absolute inset-[2px] z-[4] overflow-hidden rounded-[inherit] border-black/10 text-white dark:border-white/15 dark:text-black"
        style={{ borderWidth: 'var(--border-width)', backgroundColor: '#000000' }}
        aria-hidden="true"
      >
        <svg
          width="100%"
          height="100%"
          preserveAspectRatio="none"
          viewBox="0 0 100 40"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <g clipPath="url(#clip0_hero_star)">
            <path
              d="M32.34 26.68C32.34 26.3152 32.0445 26.02 31.68 26.02C31.3155 26.02 31.02 26.3152 31.02 26.68C31.02 27.0448 31.3155 27.34 31.68 27.34C32.0445 27.34 32.34 27.0448 32.34 26.68Z"
              fill="black"
            />
          </g>
          <defs>
            <clipPath id="clip0_hero_star">
              <rect width="100" height="40" fill="white" />
            </clipPath>
          </defs>
        </svg>
      </div>
      <span className="relative z-10 inline-flex items-center gap-1 whitespace-nowrap text-white font-medium">
        GET STARTED
        <Arrow />
      </span>
    </button>
  );
}

// Request Demo secondary action button
function DemoButton({ onClick }: { onClick?: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="relative isolate inline-flex h-10 shrink-0 items-center justify-center gap-2 overflow-hidden whitespace-nowrap rounded-full border border-white/30 bg-white px-5 py-2 text-sm font-medium text-black shadow-xs transition-all cursor-pointer hover:bg-zinc-200 hover:text-black"
    >
      <span
        aria-hidden="true"
        className="pointer-events-none absolute left-[1.125rem] top-0 h-px w-[calc(100%-2.25rem)] bg-gradient-to-r from-neutral-950/0 via-neutral-500 to-neutral-950/0"
      />
      <span className="relative z-10 font-medium tracking-wide">REQUEST A DEMO</span>
    </button>
  );
}

// Running framework and security technology logos in Hero marquee
const TECH_RUNNING_LOGOS = [
  {
    name: 'React',
    icon: (
      <svg className="w-4 h-4 text-white/60 fill-none stroke-current" viewBox="-11.5 -10.23174 23 20.46348">
        <circle cx="0" cy="0" r="2.05" fill="rgba(255,255,255,0.65)" stroke="none" />
        <g stroke="rgba(255,255,255,0.65)" strokeWidth="1" fill="none">
          <ellipse rx="11" ry="4.2" />
          <ellipse rx="11" ry="4.2" transform="rotate(60)" />
          <ellipse rx="11" ry="4.2" transform="rotate(120)" />
        </g>
      </svg>
    ),
  },
  {
    name: 'Alembic',
    icon: (
      <svg className="w-4 h-4 text-amber-400 fill-none stroke-current" viewBox="0 0 24 24" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M10 2v7.31L4.1 19.3A2 2 0 0 0 5.8 22h12.4a2 2 0 0 0 1.7-2.7L14 9.31V2" />
        <path d="M8.5 2h7" />
        <path d="M7 16h10" />
      </svg>
    ),
  },
  {
    name: 'FastAPI',
    icon: (
      <svg className="w-4 h-4 fill-emerald-400" viewBox="0 0 24 24">
        <circle cx="12" cy="12" r="10" fill="#059669" fillOpacity="0.2" stroke="#10b981" strokeWidth="1.5" />
        <path d="M13 3L6 14h5l-2 7 9-12h-5l2-6z" fill="rgba(255,255,255,0.60)" />
      </svg>
    ),
  },
  {
    name: 'LangGraph',
    icon: (
      <svg className="w-4 h-4 fill-none stroke-purple-400" viewBox="0 0 24 24" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="6" cy="6" r="3" fill="#a855f7" fillOpacity="0.3" />
        <circle cx="18" cy="6" r="3" fill="#a855f7" fillOpacity="0.3" />
        <circle cx="12" cy="18" r="3" fill="#a855f7" fillOpacity="0.3" />
        <path d="M8.5 7.5L15.5 7.5" />
        <path d="M7.5 8.5L10.5 15.5" />
        <path d="M16.5 8.5L13.5 15.5" />
      </svg>
    ),
  },
  {
    name: 'JWT',
    icon: (
      <svg className="w-4 h-4 fill-none stroke-pink-400" viewBox="0 0 24 24" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
        <path d="M7 11V7a5 5 0 0 1 10 0v4" />
        <circle cx="12" cy="16.5" r="1.5" fill="#ffffff" />
      </svg>
    ),
  },
  {
    name: 'PostgreSQL',
    icon: (
      <svg className="w-4 h-4 text-sky-400 fill-none stroke-current" viewBox="0 0 24 24" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <ellipse cx="12" cy="5" rx="9" ry="3" />
        <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
        <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
      </svg>
    ),
  },
  {
    name: 'Docker',
    icon: (
      <svg className="w-4 h-4 text-blue-400 fill-current" viewBox="0 0 24 24">
        <path d="M13.983 11.078h2.119a.186.186 0 00.186-.185V9.006a.186.186 0 00-.186-.186h-2.119a.185.185 0 00-.185.185v1.888c0 .102.083.185.185.185m-2.954-5.43h2.118a.186.186 0 00.186-.186V3.574a.186.186 0 00-.186-.185h-2.118a.185.185 0 00-.185.185v1.888c0 .102.082.185.185.185m0 2.716h2.118a.187.187 0 00.186-.186V6.29a.186.186 0 00-.186-.185h-2.118a.185.185 0 00-.185.185v1.887c0 .102.082.186.185.186m-2.93 0h2.12a.186.186 0 00.184-.186V6.29a.185.185 0 00-.185-.185H8.1a.185.185 0 00-.185.185v1.887c0 .102.083.186.185.186m-2.964 0h2.119a.186.186 0 00.185-.186V6.29a.185.185 0 00-.185-.185H5.136a.186.186 0 00-.186.185v1.887c0 .102.084.186.186.186m5.893 2.714h2.119a.186.186 0 00.186-.185V9.006a.186.186 0 00-.186-.186h-2.119a.185.185 0 00-.185.185v1.888c0 .102.082.185.185.185m-2.93 0h2.12a.185.185 0 00.184-.185V9.006a.185.185 0 00-.184-.186h-2.12a.185.185 0 00-.184.185v1.888c0 .102.083.185.185.185m-2.964 0h2.119a.185.185 0 00.185-.185V9.006a.185.185 0 00-.185-.186H5.136a.186.186 0 00-.186.185v1.888c0 .102.084.185.186.185m-2.928 0h2.119a.185.185 0 00.185-.185V9.006a.185.185 0 00-.185-.186H2.208a.186.186 0 00-.186.185v1.888c0 .102.084.185.186.185m21.724-.303c-.347-.232-1.397-.306-2.2-.083-.177-.852-.777-1.503-1.637-1.78l-.348-.112-.224.286c-.468.599-.785 1.342-.924 2.164-.53-.186-1.127-.267-1.764-.267H.215a.214.214 0 00-.215.216c0 1.256.242 2.457.7 3.545.922 2.188 2.631 3.824 4.814 4.606a14.246 14.246 0 004.996 1.058c4.27 0 8.083-1.859 10.742-4.831l.243-.271-.345-.119c-.394-.136-.677-.282-.871-.448.868-.088 2.215-.494 2.825-1.725l.18-.363-.353-.176z" />
      </svg>
    ),
  },
  {
    name: 'CWE',
    icon: (
      <svg className="w-4 h-4 text-amber-400 fill-none stroke-current" viewBox="0 0 24 24" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
        <path d="M9 12l2 2 4-4" />
      </svg>
    ),
  },
  {
    name: 'Semgrep',
    icon: (
      <svg className="w-4 h-4 text-white/60 fill-none stroke-current" viewBox="0 0 24 24" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
        <polyline points="4 17 10 11 4 5" />
        <line x1="12" y1="19" x2="20" y2="19" />
      </svg>
    ),
  },
];

function LogoMarquee({ visible }: { visible: boolean }) {
  const trackRef = useRef<HTMLDivElement>(null);
  // Speeds in pixels per second. Eases toward target with inertia.
  const speed = useRef({ current: 40, target: 40 });

  useEffect(() => {
    const track = trackRef.current;
    if (!track) return;

    let pos = 0;
    let last = performance.now();
    let rafId: number;

    const tick = (now: number) => {
      // Clamp dt so background tab switching doesn't jump the loop
      const dt = Math.min((now - last) / 1000, 0.1);
      last = now;

      // Exponential ease toward target speed — frame-rate independent physics
      const ease = 1 - Math.exp(-dt * 6);
      speed.current.current += (speed.current.target - speed.current.current) * ease;

      pos += speed.current.current * dt;

      // Wrap at half track width since logos are duplicated
      const half = track.scrollWidth / 2;
      if (half > 0 && pos >= half) pos -= half;
      if (pos < 0) pos += half;

      track.style.transform = `translate3d(${-pos}px, 0, 0)`;
      rafId = requestAnimationFrame(tick);
    };

    rafId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafId);
  }, []);

  const loop = [...TECH_RUNNING_LOGOS, ...TECH_RUNNING_LOGOS];

  return (
    <div
      className={`w-full transition-all delay-500 duration-700 ${
        visible ? 'translate-y-0 opacity-100' : 'translate-y-4 opacity-0'
      }`}
    >
      <div className="mx-auto w-[calc(100%-2rem)] max-w-[1344px] overflow-hidden py-2 [mask-image:linear-gradient(to_right,transparent,black_15%,black_85%,transparent)]">
        <div
          className="overflow-hidden"
          onMouseEnter={() => {
            speed.current.target = 130;
          }}
          onMouseLeave={() => {
            speed.current.target = 40;
          }}
        >
          <div
            ref={trackRef}
            className="flex w-max items-center will-change-transform"
            style={{ gap: '48px' }}
          >
            {loop.map((item, i) => (
              <div
                key={`${item.name}-${i}`}
                className="flex items-center gap-2 text-white/70 hover:text-white font-medium text-[13.5px] sm:text-[14.5px] tracking-tight select-none whitespace-nowrap transition-colors cursor-default"
              >
                {item.icon}
                <span className="font-semibold">{item.name}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

interface HeroProps {
  onGetStarted?: () => void;
  onRequestDemo?: () => void;
}

export default function Hero({ onGetStarted, onRequestDemo }: HeroProps) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  return (
    <section className="relative flex h-[100dvh] w-full flex-col justify-between overflow-hidden bg-black pt-20 sm:pt-24 pb-4 sm:pb-6">
      {/* Vortex background layer: 3D interactive particle simulation */}
      <div className="absolute inset-0 z-0 overflow-hidden pointer-events-none">
        <div className="pointer-events-auto w-full h-full">
          <Vortex
            background="#000000"
            lineOptions={{ color: '#ffffff', glow: 10 }}
            dotOptions={{ color: '#ffffff', glow: 10, size: 6 }}
            cometOptions={{ color: '#eca8d6', glow: 6 }}
            repel
          />
        </div>
        {/* Gradient overlays for text contrast and depth */}
        <div className="pointer-events-none absolute inset-0 bg-gradient-to-r from-black/70 via-black/30 to-transparent" />
        <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-black/50 via-transparent to-black/80" />
      </div>

      {/* Hero center content (Headline, Subtitle, CTA buttons) */}
      <div className="relative z-10 my-auto mx-auto flex w-full max-w-4xl flex-col items-center px-4 text-center">
        {/* Headline */}
        <h1
          className={`font-display text-5xl md:text-6xl lg:text-7xl font-semibold leading-[1.05] tracking-tight text-white transition-all duration-700 ${
            mounted ? 'translate-y-0 opacity-100' : 'translate-y-3 opacity-0'
          }`}
        >
          Your Code&apos;s Got Secrets. We Find Them.
        </h1>

        {/* Subheading */}
        <p
          className={`mt-5 sm:mt-6 max-w-2xl mx-auto text-center text-base md:text-lg leading-relaxed text-white/70 transition-all delay-150 duration-700 ${
            mounted ? 'translate-y-0 opacity-100' : 'translate-y-3 opacity-0'
          }`}
        >
          Vigil puts your code under the microscope. AI agents hunt down bugs, security risks, and code smells, then explain the issue, severity, and fix, so you can ship without surprises.
        </p>

        {/* CTA buttons */}
        <div
          className={`mt-6 sm:mt-8 flex flex-col sm:flex-row items-center justify-center gap-3.5 transition-all delay-200 duration-700 ${
            mounted ? 'translate-y-0 opacity-100' : 'translate-y-3 opacity-0'
          }`}
        >
          <StarButton onClick={onGetStarted} />
          <DemoButton onClick={onRequestDemo} />
        </div>
      </div>

      {/* Verified platform marquee pinned to the bottom */}
      <div className="relative z-10 w-full shrink-0">
        <LogoMarquee visible={mounted} />
      </div>
    </section>
  );
}
