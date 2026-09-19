'use client';

import React, { useEffect, useState, useRef } from 'react';
import dynamic from 'next/dynamic';
import Link from 'next/link';

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

// Infinite velocity marquee for verified platform integrations
const MARQUEE_LOGOS = [
  { src: '/images/logo-marquee/stripe.png', alt: 'Stripe Security' },
  { src: '/images/logo-marquee/vercel.png', alt: 'Vercel Deployment Gate' },
  { src: '/images/logo-marquee/bigquery.png', alt: 'BigQuery Audit Pipeline' },
  { src: '/images/logo-marquee/slack.png', alt: 'Slack Incident Alerts' },
  { src: '/images/logo-marquee/supabase.png', alt: 'Supabase Dataflow' },
  { src: '/images/logo-marquee/github.png', alt: 'GitHub Actions' },
  { src: '/images/logo-marquee/hubspot.png', alt: 'Audit Sync' },
  { src: '/images/logo-marquee/zapier.png', alt: 'Webhook Gateways' },
  { src: '/images/logo-marquee/snowflake.png', alt: 'Telemetry Lake' },
  { src: '/images/logo-marquee/aws-s3.png', alt: 'SARIF Artifacts' },
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

  const loop = [...MARQUEE_LOGOS, ...MARQUEE_LOGOS];

  return (
    <div
      className={`w-full transition-all delay-500 duration-700 ${
        visible ? 'translate-y-0 opacity-100' : 'translate-y-4 opacity-0'
      }`}
    >
      <div className="mx-auto w-[calc(100%-2rem)] max-w-[1344px] overflow-hidden py-1 [mask-image:linear-gradient(to_right,transparent,black_20%,black_80%,transparent)]">
        <div
          className="overflow-hidden"
          onMouseEnter={() => {
            speed.current.target = 140;
          }}
          onMouseLeave={() => {
            speed.current.target = 40;
          }}
        >
          <div
            ref={trackRef}
            className="flex w-max items-center will-change-transform"
            style={{ gap: '38px' }}
          >
            {loop.map((logo, i) => (
              <img
                key={`${logo.alt}-${i}`}
                alt={logo.alt}
                src={logo.src}
                width="auto"
                height="auto"
                loading="lazy"
                className="pointer-events-none h-6 sm:h-7 md:h-8 w-auto select-none opacity-70 brightness-0 grayscale invert transition-opacity hover:opacity-100"
              />
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
    <section className="relative flex h-[100dvh] w-full flex-col justify-between overflow-hidden bg-black pt-16 sm:pt-20 pb-4 sm:pb-6">
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
        {/* Verification Badge */}
        <div
          className={`mb-4 inline-flex items-center gap-2 px-3 py-1 rounded-full border border-white/10 bg-white/[0.04] text-xs font-mono text-zinc-300 transition-all duration-700 ${
            mounted ? 'translate-y-0 opacity-100' : 'translate-y-2 opacity-0'
          }`}
        >
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          <span>AUTOMATED CODE REVIEW</span>
        </div>

        {/* Headline */}
        <h1
          className={`font-display text-5xl md:text-6xl lg:text-7xl font-semibold leading-[1.05] tracking-tight text-white transition-all duration-700 ${
            mounted ? 'translate-y-0 opacity-100' : 'translate-y-3 opacity-0'
          }`}
        >
          Find bugs and security issues before they reach production.
        </h1>

        {/* Subheading */}
        <p
          className={`mt-5 sm:mt-6 max-w-2xl mx-auto text-center text-base md:text-lg leading-relaxed text-white/70 transition-all delay-150 duration-700 ${
            mounted ? 'translate-y-0 opacity-100' : 'translate-y-3 opacity-0'
          }`}
        >
          Vigil reviews your Python, JavaScript, and TypeScript code using specialized review agents and proven static analysis tools. Every issue comes with a clear explanation, a suggested fix, and a severity rating — so you can fix problems early and ship with confidence.
        </p>

        {/* CTA buttons */}
        <div
          className={`mt-6 sm:mt-8 flex flex-col sm:flex-row items-center justify-center gap-3.5 transition-all delay-200 duration-700 ${
            mounted ? 'translate-y-0 opacity-100' : 'translate-y-3 opacity-0'
          }`}
        >
          <StarButton onClick={onGetStarted} />
          <DemoButton onClick={onRequestDemo} />
          <Link
            href="/dashboard"
            className="text-xs font-mono tracking-wider text-zinc-400 hover:text-white uppercase px-3 py-2 transition-colors flex items-center gap-1.5"
          >
            SecOps Console →
          </Link>
        </div>
      </div>

      {/* Verified platform marquee pinned to the bottom */}
      <div className="relative z-10 w-full shrink-0">
        <LogoMarquee visible={mounted} />
      </div>
    </section>
  );
}
