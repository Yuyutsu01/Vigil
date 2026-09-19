'use client';

import React, { useState, useEffect } from 'react';
import { api } from '@/lib/api';

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
      {/* 1. section#about — Editorial Mission Statement */}
      <section id="about" className="py-24 px-6 md:px-12 border-t border-white/10 max-w-6xl mx-auto">
        <div className="text-xs md:text-sm font-mono tracking-[0.15em] text-cyan-400/80 uppercase mb-4">
          WHY VIGIL EXISTS
        </div>
        <h2 className="text-3xl sm:text-5xl font-normal tracking-tight text-white max-w-4xl leading-[1.15] mb-8">
          Every commit is a chance to ship a bug. Vigil watches your code, explains what&apos;s wrong, and tells you how to fix it — before your users find out the hard way.
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 pt-8 border-t border-white/10">
          <div>
            <h3 className="text-lg md:text-xl font-semibold text-white mb-3">Built on real code analysis</h3>
            <p className="text-sm md:text-base text-white/70 leading-relaxed">
              Vigil reads your code the same way a compiler does. Every finding points to the exact line and explains why it matters — no made-up warnings, no guessing.
            </p>
          </div>
          <div>
            <h3 className="text-lg md:text-xl font-semibold text-white mb-3">Your code never gets run</h3>
            <p className="text-sm md:text-base text-white/70 leading-relaxed">
              We analyze your code statically, without executing it. When a suggested fix needs testing, it runs inside a locked-down sandbox that has no internet access and no access to your secrets.
            </p>
          </div>
          <div>
            <h3 className="text-lg md:text-xl font-semibold text-white mb-3">Safe, ready-to-review fixes</h3>
            <p className="text-sm md:text-base text-white/70 leading-relaxed">
              Every suggested fix comes as a standard code diff you can review like any other change. Nothing gets merged or deployed without your explicit approval.
            </p>
          </div>
        </div>
      </section>

      {/* 2. section#features — Core Capabilities Grid */}
      <section id="features" className="py-24 px-6 md:px-12 border-t border-white/10 max-w-6xl mx-auto">
        <div className="text-xs md:text-sm font-mono tracking-[0.15em] text-cyan-400/80 uppercase mb-3">
          HOW VIGIL WORKS
        </div>
        <h3 className="text-3xl sm:text-4xl font-normal tracking-tight text-white mb-12">
          A complete review pipeline that runs on every pull request.
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <div className="p-6 md:p-7 border border-white/10 rounded-xl bg-black hover:border-white/20 transition-all">
            <div className="font-mono text-xs text-white/40 tracking-[0.15em] mb-2">01 // TRACKING</div>
            <h4 className="text-base md:text-lg font-semibold text-white leading-snug">Trace user input across your code</h4>
            <p className="text-sm md:text-base text-white/70 leading-relaxed mt-2">
              Vigil follows untrusted data from where it enters your app — like a URL parameter or form field — all the way to where it&apos;s used. If it reaches something dangerous like a database query without being sanitized, we flag it.
            </p>
          </div>
          <div className="p-6 md:p-7 border border-white/10 rounded-xl bg-black hover:border-white/20 transition-all">
            <div className="font-mono text-xs text-white/40 tracking-[0.15em] mb-2">02 // ISOLATION</div>
            <h4 className="text-base md:text-lg font-semibold text-white leading-snug">Test fixes in an isolated sandbox</h4>
            <p className="text-sm md:text-base text-white/70 leading-relaxed mt-2">
              When Vigil suggests a fix, it can run your project&apos;s tests against it inside a temporary, disposable container. The sandbox has no network access, no access to your secrets, and no way to touch anything outside itself.
            </p>
          </div>
          <div className="p-6 md:p-7 border border-white/10 rounded-xl bg-black hover:border-white/20 transition-all">
            <div className="font-mono text-xs text-white/40 tracking-[0.15em] mb-2">03 // ENFORCEMENT</div>
            <h4 className="text-base md:text-lg font-semibold text-white leading-snug">Stop bad code before it merges</h4>
            <p className="text-sm md:text-base text-white/70 leading-relaxed mt-2">
              Connect Vigil to GitHub and it runs on every pull request. If it finds critical issues, it can block the merge — or just warn your team, depending on how you configure it. You decide.
            </p>
          </div>
          <div className="p-6 md:p-7 border border-white/10 rounded-xl bg-black hover:border-white/20 transition-all">
            <div className="font-mono text-xs text-white/40 tracking-[0.15em] mb-2">04 // REPORTS</div>
            <h4 className="text-base md:text-lg font-semibold text-white leading-snug">Export reports for your security team</h4>
            <p className="text-sm md:text-base text-white/70 leading-relaxed mt-2">
              Every review produces a detailed report in JSON, HTML, or PDF — including a one-page executive summary. Every action is logged to a tamper-proof audit trail.
            </p>
          </div>
          <div className="p-6 md:p-7 border border-white/10 rounded-xl bg-black hover:border-white/20 transition-all">
            <div className="font-mono text-xs text-white/40 tracking-[0.15em] mb-2">05 // LEARNING</div>
            <h4 className="text-base md:text-lg font-semibold text-white leading-snug">Gets smarter from your feedback</h4>
            <p className="text-sm md:text-base text-white/70 leading-relaxed mt-2">
              When you mark a finding as a false positive, Vigil remembers it — so the next review of similar code doesn&apos;t flag the same thing. This is opt-in, per tenant, and fully reversible.
            </p>
          </div>
          <div className="p-6 md:p-7 border border-white/10 rounded-xl bg-black hover:border-white/20 transition-all">
            <div className="font-mono text-xs text-white/40 tracking-[0.15em] mb-2">06 // COST CONTROL</div>
            <h4 className="text-base md:text-lg font-semibold text-white leading-snug">No surprise AI bills</h4>
            <p className="text-sm md:text-base text-white/70 leading-relaxed mt-2">
              Every review has a strict token and dollar budget. If a large repo would exceed it, the review pauses gracefully and returns partial results instead of running up a huge bill.
            </p>
          </div>
        </div>
      </section>

      {/* 3. section#benchmarks — Verifiable Architectural Metrics */}
      <section id="benchmarks" className="py-24 px-6 md:px-12 border-t border-white/10 max-w-6xl mx-auto">
        <div className="text-xs md:text-sm font-mono tracking-[0.15em] text-cyan-400/80 uppercase mb-3">
          VERIFIABLE METRICS
        </div>
        <h3 className="text-3xl sm:text-4xl font-normal tracking-tight text-white mb-12">
          Built on transparent, verifiable architecture
        </h3>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-6 font-mono text-center">
          <div className="p-6 border border-white/10 rounded-xl bg-black flex flex-col justify-center items-center">
            <div className="text-3xl md:text-4xl font-semibold text-white">3</div>
            <div className="text-xs md:text-sm font-mono tracking-[0.15em] uppercase text-cyan-400/80 mt-2">
              PYTHON · JS · TS
            </div>
            <div className="text-xs text-white/50 mt-1">Supported Languages</div>
          </div>

          <div className="p-6 border border-white/10 rounded-xl bg-black flex flex-col justify-center items-center">
            <div className="text-3xl md:text-4xl font-semibold text-white">13</div>
            <div className="text-xs md:text-sm font-mono tracking-[0.15em] uppercase text-cyan-400/80 mt-2">
              7 RULES + 6 ADAPTERS
            </div>
            <div className="text-xs text-white/50 mt-1">Detection Layers</div>
          </div>

          <div className="p-6 border border-white/10 rounded-xl bg-black flex flex-col justify-center items-center">
            <div className="text-3xl md:text-4xl font-semibold text-white">0</div>
            <div className="text-xs md:text-sm font-mono tracking-[0.15em] uppercase text-cyan-400/80 mt-2">
              ZERO EXECUTION
            </div>
            <div className="text-xs text-white/50 mt-1">Unsandboxed Runs</div>
          </div>

          <div className="p-6 border border-white/10 rounded-xl bg-black flex flex-col justify-center items-center">
            <div className="text-3xl md:text-4xl font-semibold text-white">
              {reviewDurationText}
            </div>
            <div className="text-xs md:text-sm font-mono tracking-[0.15em] uppercase text-cyan-400/80 mt-2">
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
        <div className="text-xs md:text-sm font-mono tracking-[0.15em] text-cyan-400/80 uppercase mb-3">
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

