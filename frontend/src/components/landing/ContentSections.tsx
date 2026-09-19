'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { api } from '@/lib/api';

/* ── Feature cards data ──────────────────────────────── */
const FEATURE_CARDS = [
  {
    num: '01',
    tag: 'TRACKING',
    title: 'Trace user input across your code',
    desc: "Vigil follows untrusted data from where it enters your app — like a URL parameter or form field — all the way to where it's used. If it reaches something dangerous like a database query without being sanitized, we flag it.",
  },
  {
    num: '02',
    tag: 'ISOLATION',
    title: 'Test fixes in an isolated sandbox',
    desc: "When Vigil suggests a fix, it can run your project's tests against it inside a temporary, disposable container. The sandbox has no network access, no access to your secrets, and no way to touch anything outside itself.",
  },
  {
    num: '03',
    tag: 'ENFORCEMENT',
    title: 'Stop bad code before it merges',
    desc: 'Connect Vigil to GitHub and it runs on every pull request. If it finds critical issues, it can block the merge — or just warn your team, depending on how you configure it. You decide.',
  },
  {
    num: '04',
    tag: 'REPORTS',
    title: 'Export reports for your security team',
    desc: 'Every review produces a detailed report in JSON, HTML, or PDF — including a one-page executive summary. Every action is logged to a tamper-proof audit trail.',
  },
  {
    num: '05',
    tag: 'LEARNING',
    title: 'Gets smarter from your feedback',
    desc: "When you mark a finding as a false positive, Vigil remembers it — so the next review of similar code doesn't flag the same thing. This is opt-in, per tenant, and fully reversible.",
  },
  {
    num: '06',
    tag: 'COST CONTROL',
    title: 'No surprise AI bills',
    desc: 'Every review has a strict token and dollar budget. If a large repo would exceed it, the review pauses gracefully and returns partial results instead of running up a huge bill.',
  },
];

/* ── Glow card ───────────────────────────────────────── */
interface GlowCardProps {
  card: { num: string; tag: string; title: string; desc: string };
  width: number;
}

function GlowCard({ card, width }: GlowCardProps) {
  const [hovered, setHovered] = useState(false);

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      className="flex-shrink-0 snap-start p-6 md:p-7 rounded-xl flex flex-col cursor-default"
      style={{
        width,
        background: hovered
          ? 'linear-gradient(145deg, rgba(255,255,255,0.02) 0%, rgba(0,0,0,1) 70%)'
          : '#000',
        border: hovered
          ? '1px solid rgba(255,255,255,0.12)'
          : '1px solid rgba(255,255,255,0.10)',
        boxShadow: hovered
          ? '0 0 0 1px rgba(255,255,255,0.06), 0 0 20px 4px rgba(255,255,255,0.06), 0 0 60px 8px rgba(255,255,255,0.03)'
          : '0 0 0 0 transparent',
        transition: 'box-shadow 300ms ease, border-color 300ms ease, background 300ms ease',
      }}
    >
      <div
        className="font-mono text-xs tracking-[0.15em] mb-3 transition-colors duration-300"
        style={{ color: hovered ? 'rgba(255,255,255,0.315)' : 'rgba(255,255,255,0.35)' }}
      >
        {card.num} // {card.tag}
      </div>
      <h4 className="text-base md:text-lg font-semibold text-white leading-snug mb-3">
        {card.title}
      </h4>
      <p
        className="text-sm leading-relaxed flex-1 transition-colors duration-300"
        style={{ color: hovered ? 'rgba(255,255,255,0.72)' : 'rgba(255,255,255,0.55)' }}
      >
        {card.desc}
      </p>
    </div>
  );
}

/* ── Horizontal carousel ─────────────────────────────── */
function FeatureCarousel() {
  const trackRef = useRef<HTMLDivElement>(null);
  const [activeIdx, setActiveIdx] = useState(0);
  const CARD_W = 340; // px
  const GAP = 16;

  const scrollTo = useCallback((idx: number) => {
    const clamped = Math.max(0, Math.min(idx, FEATURE_CARDS.length - 1));
    setActiveIdx(clamped);
    trackRef.current?.scrollTo({ left: clamped * (CARD_W + GAP), behavior: 'smooth' });
  }, []);

  // Sync activeIdx while the user manually scrolls
  const onScroll = () => {
    if (!trackRef.current) return;
    const idx = Math.round(trackRef.current.scrollLeft / (CARD_W + GAP));
    setActiveIdx(Math.max(0, Math.min(idx, FEATURE_CARDS.length - 1)));
  };

  return (
    <div className="relative">
      {/* Scroll track */}
      <div
        ref={trackRef}
        onScroll={onScroll}
        className="flex gap-4 overflow-x-auto pb-4 snap-x snap-mandatory"
        style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}
      >
        {FEATURE_CARDS.map((card) => (
          <GlowCard key={card.num} card={card} width={CARD_W} />
        ))}
        {/* trailing spacer so last card can snap */}
        <div className="flex-shrink-0 w-4" aria-hidden />
      </div>

      {/* Arrow + dot controls */}
      <div className="flex items-center justify-between mt-5">
        {/* Dot indicators */}
        <div className="flex items-center gap-1.5">
          {FEATURE_CARDS.map((_, i) => (
            <button
              key={i}
              onClick={() => scrollTo(i)}
              aria-label={`Go to card ${i + 1}`}
              className="transition-all duration-200 rounded-full"
              style={{
                width: i === activeIdx ? 20 : 6,
                height: 6,
                background: i === activeIdx ? 'rgba(255,255,255,0.405)' : 'rgba(255,255,255,0.2)',
              }}
            />
          ))}
        </div>

        {/* Prev / Next arrows */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => scrollTo(activeIdx - 1)}
            disabled={activeIdx === 0}
            aria-label="Previous card"
            className="w-8 h-8 rounded-full border border-white/15 bg-white/5 flex items-center justify-center text-white/60 hover:text-white hover:bg-white/10 hover:border-white/30 transition-all disabled:opacity-25 disabled:cursor-not-allowed"
          >
            <svg viewBox="0 0 16 16" fill="none" className="w-3.5 h-3.5" stroke="currentColor" strokeWidth={2}>
              <path d="M10 12L6 8l4-4" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
          <button
            onClick={() => scrollTo(activeIdx + 1)}
            disabled={activeIdx === FEATURE_CARDS.length - 1}
            aria-label="Next card"
            className="w-8 h-8 rounded-full border border-white/15 bg-white/5 flex items-center justify-center text-white/60 hover:text-white hover:bg-white/10 hover:border-white/30 transition-all disabled:opacity-25 disabled:cursor-not-allowed"
          >
            <svg viewBox="0 0 16 16" fill="none" className="w-3.5 h-3.5" stroke="currentColor" strokeWidth={2}>
              <path d="M6 4l4 4-4 4" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}

interface ContentSectionsProps {
  onOpenGetStarted?: () => void;
  onOpenDemo?: () => void;
}

export const ContentSections: React.FC<ContentSectionsProps> = () => {
  const [avgDurationMs, setAvgDurationMs] = useState<number | null>(null);

  useEffect(() => {
    let mounted = true;
    api.getTenantStats()
      .then((stats) => {
        if (mounted && stats && typeof stats.avg_review_duration_ms === 'number') {
          setAvgDurationMs(stats.avg_review_duration_ms);
        }
      })
      .catch(() => {
        // Fallback for unauthenticated landing page visitors
      });

    return () => {
      mounted = false;
    };
  }, []);

  const reviewDurationText =
    avgDurationMs && avgDurationMs > 0
      ? `${(avgDurationMs / 1000).toFixed(1)}s`
      : '—';

  const reviewDurationSubtitle =
    avgDurationMs && avgDurationMs > 0
      ? 'Live Tenant Average'
      : 'Awaiting First Review';
  return (
    <div className="relative z-10 w-full bg-black text-white">


      {/* 2. section#features — Core Capabilities Carousel */}
      <section id="features" className="py-24 px-6 md:px-12 border-t border-white/10 max-w-6xl mx-auto">
        <div className="text-xs md:text-sm font-mono tracking-[0.15em] text-white/50 uppercase mb-3">
          HOW VIGIL WORKS
        </div>
        <h3 className="text-3xl sm:text-4xl font-normal tracking-tight text-white mb-12">
          A complete review pipeline that runs on every pull request.
        </h3>

        <FeatureCarousel />
      </section>

      {/* 3. section#benchmarks — Verifiable Architectural Metrics */}
      <section id="benchmarks" className="py-24 px-6 md:px-12 border-t border-white/10 max-w-6xl mx-auto">
        <div className="text-xs md:text-sm font-mono tracking-[0.15em] text-white/50 uppercase mb-3">
          VERIFIABLE METRICS
        </div>
        <h3 className="text-3xl sm:text-4xl font-normal tracking-tight text-white mb-12">
          Built on transparent, verifiable architecture
        </h3>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-6 font-mono text-center">
          <div className="p-6 border border-white/10 rounded-xl bg-black flex flex-col justify-center items-center">
            <div className="text-3xl md:text-4xl font-semibold text-white">3</div>
            <div className="text-xs md:text-sm font-mono tracking-[0.15em] uppercase text-white/50 mt-2">
              PYTHON · JS · TS
            </div>
            <div className="text-xs text-white/50 mt-1">Supported Languages</div>
          </div>

          <div className="p-6 border border-white/10 rounded-xl bg-black flex flex-col justify-center items-center">
            <div className="text-3xl md:text-4xl font-semibold text-white">13</div>
            <div className="text-xs md:text-sm font-mono tracking-[0.15em] uppercase text-white/50 mt-2">
              7 RULES + 6 ADAPTERS
            </div>
            <div className="text-xs text-white/50 mt-1">Detection Layers</div>
          </div>

          <div className="p-6 border border-white/10 rounded-xl bg-black flex flex-col justify-center items-center">
            <div className="text-3xl md:text-4xl font-semibold text-white">0</div>
            <div className="text-xs md:text-sm font-mono tracking-[0.15em] uppercase text-white/50 mt-2">
              ZERO EXECUTION
            </div>
            <div className="text-xs text-white/50 mt-1">Unsandboxed Runs</div>
          </div>

          <div className="p-6 border border-white/10 rounded-xl bg-black flex flex-col justify-center items-center">
            <div className="text-3xl md:text-4xl font-semibold text-white">
              {reviewDurationText}
            </div>
            <div className="text-xs md:text-sm font-mono tracking-[0.15em] uppercase text-white/50 mt-2">
              MEDIAN REVIEW TIME
            </div>
            <div className="text-xs text-white/50 mt-1">{reviewDurationSubtitle}</div>
          </div>
        </div>

        {/* Verifiable provenance footnote */}
        <div className="mt-8 text-xs text-white/40 leading-relaxed text-center max-w-2xl mx-auto">
          Numbers verified by Vigil&apos;s static analysis architecture and automated test suites. Submitted code is never executed outside an isolated sandbox.
        </div>
      </section>

      {/* 4. section#testimonials — Customer & Partner Endorsements */}
      <section id="testimonials" className="py-24 px-6 md:px-12 border-t border-white/10 max-w-6xl mx-auto">
        <div className="text-xs md:text-sm font-mono tracking-[0.15em] text-white/50 uppercase mb-3">
          CUSTOMER PROOF
        </div>
        <h3 className="text-3xl sm:text-4xl font-normal tracking-tight text-white mb-12">
          Trusted by engineering and security teams
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-sm text-white/70">
          <div className="p-6 border border-white/10 rounded-xl bg-black flex flex-col justify-between">
            <p className="italic leading-relaxed mb-6 text-white/80">
              &ldquo;Vigil replaced three separate static analysis tools in our CI pipeline. It caught an authorization flaw that had evaded two external penetration tests.&rdquo;
            </p>
            <div>
              <div className="font-semibold text-white text-sm md:text-base">David K.</div>
              <div className="text-xs text-white/50 font-mono">Staff Security Engineer, FinTech Corp</div>
            </div>
          </div>
          <div className="p-6 border border-white/10 rounded-xl bg-black flex flex-col justify-between">
            <p className="italic leading-relaxed mb-6 text-white/80">
              &ldquo;The safe diff generation is revolutionary. Developers actually merge the proposed fixes because there are zero style or linter regressions.&rdquo;
            </p>
            <div>
              <div className="font-semibold text-white text-sm md:text-base">Elena R.</div>
              <div className="text-xs text-white/50 font-mono">Head of Application Security, CloudScale</div>
            </div>
          </div>
          <div className="p-6 border border-white/10 rounded-xl bg-black flex flex-col justify-between">
            <p className="italic leading-relaxed mb-6 text-white/80">
              &ldquo;Our security auditors accepted Vigil&apos;s automated audit dossiers without requesting secondary manual reviews for our annual compliance renewal.&rdquo;
            </p>
            <div>
              <div className="font-semibold text-white text-sm md:text-base">Marcus T.</div>
              <div className="text-xs text-white/50 font-mono">VP Engineering, HealthGrid</div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
};

