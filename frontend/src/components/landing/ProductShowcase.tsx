'use client';

import React, { useState, useEffect, useRef } from 'react';

/* ── Code Editor Mock ─────────────────────────────── */
function CodeEditorMock() {
  const CODE_LINES = [
    'def get_user(user_id):',
    "    query = f\"SELECT * FROM users",
    "             WHERE id = '{user_id}'\"",
    '    return db.execute(query)',
    '',
    'def main():',
    '    user = get_user(input("ID: "))',
    '    print(user)',
  ];
  const [activeTab, setActiveTab] = useState('issues');
  const [showPanel, setShowPanel] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setShowPanel(true), 900);
    return () => clearTimeout(t);
  }, []);

  return (
    <div className="relative rounded-2xl overflow-hidden border border-white/10 shadow-2xl" style={{ background: '#0d1117' }}>
      <div className="flex items-center gap-1.5 px-4 py-3 border-b border-white/10" style={{ background: '#161b22' }}>
        <span className="w-3 h-3 rounded-full bg-[#ff5f57]" />
        <span className="w-3 h-3 rounded-full bg-[#febc2e]" />
        <span className="w-3 h-3 rounded-full bg-[#28c840]" />
        <span className="ml-auto text-[10px] font-mono text-white/30 tracking-widest">Vigil Static Security Engine</span>
      </div>
      <div className="flex" style={{ minHeight: 300 }}>
        <div className="flex-1 overflow-hidden">
          <div className="flex items-center gap-1.5 px-3 py-2 border-b border-white/10" style={{ background: '#161b22' }}>
            <svg className="w-3.5 h-3.5 text-blue-400" viewBox="0 0 20 20" fill="currentColor">
              <path d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z"/>
            </svg>
            <span className="text-xs font-mono text-white/80">user.py</span>
          </div>
          <div className="font-mono text-[11px] leading-[1.75] py-3 select-none">
            {CODE_LINES.map((line, i) => {
              const isVuln = i === 1 || i === 2;
              return (
                <div
                  key={i}
                  className="flex items-start"
                  style={{
                    background: isVuln ? 'rgba(255,80,80,0.08)' : 'transparent',
                    borderLeft: isVuln ? '2px solid rgba(255,80,80,0.45)' : '2px solid transparent',
                    paddingLeft: 12,
                    paddingRight: 12,
                  }}
                >
                  <span className="w-6 text-right mr-4 text-[10px] text-white/20 select-none flex-shrink-0 mt-px">{i + 1}</span>
                  <span style={{ color: isVuln ? '#ff8a8a' : (i === 0 || i === 5) ? '#c678dd' : '#abb2bf' }}>{line || ' '}</span>
                </div>
              );
            })}
          </div>
        </div>
        <div
          className="border-l border-white/10 flex flex-col overflow-hidden transition-all duration-700"
          style={{ width: showPanel ? 210 : 0, opacity: showPanel ? 1 : 0, background: '#0d1117', flexShrink: 0 }}
        >
          <div className="flex border-b border-white/10 text-[10px] font-mono">
            {['issues', 'explanation', 'fix'].map(tab => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={'px-3 py-2 capitalize transition-colors ' + (activeTab === tab ? 'text-white border-b-2 border-white/30' : 'text-white/35 hover:text-white/60')}
              >
                {tab.charAt(0).toUpperCase() + tab.slice(1)}
              </button>
            ))}
          </div>
          <div className="flex-1 p-3">
            {activeTab === 'issues' && (
              <div>
                <div className="flex items-start gap-2 p-2.5 rounded-lg mb-2" style={{ background: 'rgba(255,80,80,0.1)', border: '1px solid rgba(255,80,80,0.22)' }}>
                  <svg className="w-3.5 h-3.5 text-red-400 flex-shrink-0 mt-0.5" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd"/>
                  </svg>
                  <div>
                    <div className="text-[10px] font-semibold text-red-400">SQL Injection Risk</div>
                    <div className="text-[9px] text-white/55 mt-0.5 leading-relaxed">User input is directly inserted into the SQL query.</div>
                  </div>
                </div>
                <button onClick={() => setActiveTab('fix')} className="w-full py-1.5 rounded-lg text-[10px] font-mono font-semibold text-white transition-colors" style={{ background: 'rgba(255,255,255,0.07)', border: '1px solid rgba(255,255,255,0.12)' }}>
                  Show fix &rarr;
                </button>
              </div>
            )}
            {activeTab === 'explanation' && (
              <div className="text-[9px] text-white/55 leading-relaxed space-y-2">
                <p>The <code className="text-white/60">user_id</code> flows into an f-string SQL query without sanitisation.</p>
                <p>An attacker can craft input like <code className="text-red-400">1&apos; OR &apos;1&apos;=&apos;1</code> to dump the users table.</p>
                <p className="text-white/30 mt-2">CWE-89 &middot; Severity: Critical &middot; OWASP A03</p>
              </div>
            )}
            {activeTab === 'fix' && (
              <div>
                <div className="text-[9px] font-mono text-white/35 mb-1.5">Suggested fix</div>
                <pre className="text-[9px] font-mono leading-relaxed rounded-lg p-2 overflow-x-auto" style={{ background: 'rgba(40,200,100,0.08)', border: '1px solid rgba(40,200,100,0.2)', color: '#98c379' }}>{`query = "SELECT * FROM users\n         WHERE id = %s"\ndb.execute(query, (user_id,))`}</pre>
                <div className="text-[8px] text-white/25 mt-1.5">Parameterised query prevents injection.</div>
              </div>
            )}
          </div>
          <div className="px-3 py-2 border-t border-white/10 flex items-center justify-between text-[8px] font-mono text-white/25">
            <span>Static AST Check</span>
            <span className="flex items-center gap-1 text-white/40">
              <svg className="w-2.5 h-2.5" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M2.166 4.999A11.954 11.954 0 0010 1.944 11.954 11.954 0 0017.834 5c.11.65.166 1.32.166 2.001 0 5.225-3.34 9.67-8 11.317C5.34 16.67 2 12.225 2 7c0-.682.057-1.35.166-2.001zm11.541 3.708a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd"/>
              </svg>
              Zero execution
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

const FEATURES = [
  { num: '01', title: 'Real code analysis', desc: 'Find security risks, logic errors, and bad practices. Every finding maps to the exact line.' },
  { num: '02', title: 'Your code never gets run', desc: 'Fully static analysis. Your code stays safe and private. No execution, no data leaks.' },
  { num: '03', title: 'Ready-to-review fixes', desc: 'Clear explanations and actionable suggestions — so your team ships faster.' },
];

export function ProductShowcase({ onGetStarted, onRequestDemo }: { onGetStarted?: () => void; onRequestDemo?: () => void }) {
  const ref = useRef<HTMLElement>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const obs = new IntersectionObserver(([e]) => { if (e.isIntersecting) setVisible(true); }, { threshold: 0.08 });
    if (ref.current) obs.observe(ref.current);
    return () => obs.disconnect();
  }, []);

  return (
    <section ref={ref} id="product-showcase" className="relative w-full bg-black border-t border-white/10 overflow-hidden">
      <div className="pointer-events-none absolute inset-0" style={{ background: 'radial-gradient(ellipse 55% 45% at 72% 50%, rgba(255,255,255,0.02) 0%, transparent 70%)' }} />
      <div className="max-w-7xl mx-auto px-6 md:px-14 py-24 md:py-32">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">
          <div className="transition-all duration-700" style={{ opacity: visible ? 1 : 0, transform: visible ? 'none' : 'translateY(30px)' }}>
            <div className="text-xs font-mono tracking-[0.2em] text-white/45 uppercase mb-5">Cleaner Code.&nbsp;&nbsp;Fewer Surprises.</div>
            <h2 className="text-4xl sm:text-5xl xl:text-[3.5rem] font-bold tracking-tight text-white leading-[1.07] mb-6">
              Every commit is a chance to ship a bug.
            </h2>
            <p className="text-base md:text-lg text-white/55 leading-relaxed max-w-md mb-8">
              Vigil watches your code, explains what&apos;s wrong, and tells you how to fix it &mdash; before your users find out the hard way.
            </p>
            <div className="flex flex-wrap gap-3 mb-10">
              <button
                onClick={onGetStarted}
                className="group flex items-center gap-2 px-6 py-3 rounded-xl text-sm font-semibold text-black transition-all duration-200 hover:scale-[1.03] active:scale-[0.97]"
                style={{ background: 'linear-gradient(135deg,#e0e0e0,#fff)' }}
              >
                Get started
                <svg className="w-4 h-4 transition-transform group-hover:translate-x-0.5" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clipRule="evenodd"/>
                </svg>
              </button>

            </div>
            <div className="flex flex-wrap items-center gap-4 text-[11px] font-mono text-white/28 tracking-wider">
              <span>Works with your IDE</span>
              <span className="w-1 h-1 rounded-full bg-white/18" />
              <span>No code execution</span>
              <span className="w-1 h-1 rounded-full bg-white/18" />
              <span>Developer first</span>
            </div>
          </div>
          <div className="transition-all duration-700 delay-100" style={{ opacity: visible ? 1 : 0, transform: visible ? 'none' : 'translateY(30px)' }}>
            <CodeEditorMock />
          </div>
        </div>
      </div>
      <div className="border-t border-white/10">
        <div className="max-w-7xl mx-auto px-6 md:px-14 py-16 grid grid-cols-1 md:grid-cols-3 gap-10">
          {FEATURES.map((f, i) => (
            <div
              key={f.num}
              className="transition-all duration-700"
              style={{ opacity: visible ? 1 : 0, transform: visible ? 'none' : 'translateY(18px)', transitionDelay: `${180 + i * 90}ms` }}
            >
              <div className="text-xs font-mono text-white/22 tracking-[0.2em] mb-3">{f.num}</div>
              <h3 className="text-lg font-bold text-white mb-2">{f.title}</h3>
              <p className="text-sm text-white/50 leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}