import React from 'react';

interface ContentSectionsProps {
  onOpenGetStarted?: () => void;
  onOpenDemo?: () => void;
}

export const ContentSections: React.FC<ContentSectionsProps> = () => {
  return (
    <div className="relative z-10 w-full bg-black text-white">
      {/* 1. section#about — Editorial Mission Statement */}
      <section id="about" className="py-24 px-6 md:px-12 border-t border-white/10 max-w-6xl mx-auto">
        <div className="text-[11px] font-mono tracking-[0.2em] text-white/40 uppercase mb-4">
          AUTONOMOUS CODE VERIFICATION
        </div>
        <h2 className="text-3xl sm:text-5xl font-normal tracking-tight text-white max-w-4xl leading-[1.15] mb-8">
          Modern software security cannot rely on developer memory or slow manual audits. Vigil runs
          continuous, stateful reasoning over your code graph.
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 pt-8 border-t border-white/10 text-xs text-white/60">
          <div>
            <div className="text-white font-mono uppercase mb-2">AST-Grounded Truth</div>
            Every finding is anchored in real Abstract Syntax Tree execution paths, eliminating hallucinations and ghost vulnerabilities.
          </div>
          <div>
            <div className="text-white font-mono uppercase mb-2">Zero-Execution Guarantee</div>
            Untrusted pull requests and snippets are statically reasoned over in memory without executing third-party code.
          </div>
          <div>
            <div className="text-white font-mono uppercase mb-2">Deterministic Patches</div>
            Produces unified git diffs ready for review, guaranteed to pass type checkers and maintain backwards compatibility.
          </div>
        </div>
      </section>

      {/* 2. section#features — Core Capabilities Grid */}
      <section id="features" className="py-24 px-6 md:px-12 border-t border-white/10 max-w-6xl mx-auto">
        <div className="text-[11px] font-mono tracking-[0.2em] text-white/40 uppercase mb-3">
          PLATFORM ARCHITECTURE
        </div>
        <h3 className="text-3xl sm:text-4xl font-normal tracking-tight text-white mb-12">
          Engineering defenses built for high-throughput teams
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <div className="p-6 border border-white/10 rounded-xl bg-black hover:border-white/20 transition-all">
            <div className="font-mono text-xs text-white/40 mb-2">01 // REASONING</div>
            <h4 className="text-base font-semibold text-white mb-2">Inter-procedural Taint Tracing</h4>
            <p className="text-xs text-white/60 leading-relaxed">
              Tracks unsanitized user inputs through complex API routes, microservices, and serialization boundaries down to database sinks.
            </p>
          </div>
          <div className="p-6 border border-white/10 rounded-xl bg-black hover:border-white/20 transition-all">
            <div className="font-mono text-xs text-white/40 mb-2">02 // ISOLATION</div>
            <h4 className="text-base font-semibold text-white mb-2">gVisor MicroVM Sandboxing</h4>
            <p className="text-xs text-white/60 leading-relaxed">
              Autonomous patch candidates undergo isolated reproduction runs inside ephemeral microVMs to verify exploits and prevent regressions.
            </p>
          </div>
          <div className="p-6 border border-white/10 rounded-xl bg-black hover:border-white/20 transition-all">
            <div className="font-mono text-xs text-white/40 mb-2">03 // GATEWAY</div>
            <h4 className="text-base font-semibold text-white mb-2">Automated Pull Request Blocking</h4>
            <p className="text-xs text-white/60 leading-relaxed">
              Plugs directly into GitHub Actions and GitLab CI. Emits cryptographic status checks that halt merges on Critical and High CWEs.
            </p>
          </div>
          <div className="p-6 border border-white/10 rounded-xl bg-black hover:border-white/20 transition-all">
            <div className="font-mono text-xs text-white/40 mb-2">04 // COMPLIANCE</div>
            <h4 className="text-base font-semibold text-white mb-2">Cryptographic Audit Dossiers</h4>
            <p className="text-xs text-white/60 leading-relaxed">
              Instant SARIF v2.1.0, SOC 2 Type II, and ISO 27001 exports with SHA-256 integrity digests for auditors and compliance officers.
            </p>
          </div>
          <div className="p-6 border border-white/10 rounded-xl bg-black hover:border-white/20 transition-all">
            <div className="font-mono text-xs text-white/40 mb-2">05 // FEEDBACK</div>
            <h4 className="text-base font-semibold text-white mb-2">Continuous Learning Loop</h4>
            <p className="text-xs text-white/60 leading-relaxed">
              Engineer feedback refines false-positive rates per repository without leaking proprietary source code to public LLM foundations.
            </p>
          </div>
          <div className="p-6 border border-white/10 rounded-xl bg-black hover:border-white/20 transition-all">
            <div className="font-mono text-xs text-white/40 mb-2">06 // BUDGETING</div>
            <h4 className="text-base font-semibold text-white mb-2">Predictable Execution Budgets</h4>
            <p className="text-xs text-white/60 leading-relaxed">
              Hard governors on token counts, agent iteration loops, and cloud inference costs prevent runaway runaway spend on large mono-repos.
            </p>
          </div>
        </div>
      </section>

      {/* 3. section#benchmarks — Empirical Performance Metrics */}
      <section id="benchmarks" className="py-24 px-6 md:px-12 border-t border-white/10 max-w-6xl mx-auto">
        <div className="text-[11px] font-mono tracking-[0.2em] text-white/40 uppercase mb-3">
          EMPIRICAL BENCHMARKS
        </div>
        <h3 className="text-3xl sm:text-4xl font-normal tracking-tight text-white mb-12">
          Measured against CWE Top 25 and real-world CVE corpora
        </h3>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-6 font-mono text-center">
          <div className="p-6 border border-white/10 rounded-xl bg-black">
            <div className="text-3xl sm:text-4xl font-bold text-white mb-1">94.8%</div>
            <div className="text-xs text-white/50">PRECISION RATE</div>
          </div>
          <div className="p-6 border border-white/10 rounded-xl bg-black">
            <div className="text-3xl sm:text-4xl font-bold text-white mb-1">91.2%</div>
            <div className="text-xs text-white/50">RECALL ON CWE-TOP-25</div>
          </div>
          <div className="p-6 border border-white/10 rounded-xl bg-black">
            <div className="text-3xl sm:text-4xl font-bold text-white mb-1">&lt; 2.1%</div>
            <div className="text-xs text-white/50">FALSE POSITIVE RATIO</div>
          </div>
          <div className="p-6 border border-white/10 rounded-xl bg-black">
            <div className="text-3xl sm:text-4xl font-bold text-white mb-1">1.8s</div>
            <div className="text-xs text-white/50">AVG PR AUDIT TIME</div>
          </div>
        </div>
      </section>

      {/* 4. section#testimonials — Customer & Partner Endorsements */}
      <section id="testimonials" className="py-24 px-6 md:px-12 border-t border-white/10 max-w-6xl mx-auto">
        <div className="text-[11px] font-mono tracking-[0.2em] text-white/40 uppercase mb-3">
          FIELD VALIDATION
        </div>
        <h3 className="text-3xl sm:text-4xl font-normal tracking-tight text-white mb-12">
          Trusted by security engineers and infrastructure leads
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-xs text-white/70">
          <div className="p-6 border border-white/10 rounded-xl bg-black flex flex-col justify-between">
            <p className="italic leading-relaxed mb-6">
              &ldquo;Vigil replaced three legacy static analysis tools in our CI pipeline. It caught a critical deserialization flaw that had evaded two external pentests.&rdquo;
            </p>
            <div>
              <div className="font-semibold text-white">David K.</div>
              <div className="text-[11px] text-white/40 font-mono">Staff SecOps Engineer, FinTech Corp</div>
            </div>
          </div>
          <div className="p-6 border border-white/10 rounded-xl bg-black flex flex-col justify-between">
            <p className="italic leading-relaxed mb-6">
              &ldquo;The deterministic diff generation is revolutionary. Developers actually merge the proposed patches because there are zero style or linter regressions.&rdquo;
            </p>
            <div>
              <div className="font-semibold text-white">Elena R.</div>
              <div className="text-[11px] text-white/40 font-mono">Head of Application Security, CloudScale</div>
            </div>
          </div>
          <div className="p-6 border border-white/10 rounded-xl bg-black flex flex-col justify-between">
            <p className="italic leading-relaxed mb-6">
              &ldquo;Our auditors accepted the cryptographic SARIF dossiers without requesting secondary manual reviews for our annual SOC 2 renewal.&rdquo;
            </p>
            <div>
              <div className="font-semibold text-white">Marcus T.</div>
              <div className="text-[11px] text-white/40 font-mono">VP Engineering, HealthGrid</div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
};
