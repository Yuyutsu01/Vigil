'use client';

import React, { useState } from 'react';
import { X, Check, Copy, Terminal } from 'lucide-react';
import { useModalA11y } from '@/lib/useFocusTrap';
import { focusRing } from '@/lib/styles';

interface GetStartedModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const GetStartedModal: React.FC<GetStartedModalProps> = ({
  isOpen,
  onClose,
}) => {
  const modalRef = useModalA11y(isOpen, onClose);
  const [framework, setFramework] = useState<'python' | 'node' | 'curl'>('python');
  const [copied, setCopied] = useState(false);
  const [email, setEmail] = useState('');
  const [submitted, setSubmitted] = useState(false);

  if (!isOpen) return null;

  const codeSnippets = {
    python: `import os
from vigil_sdk import VigilClient

# Initialize Vigil AST Engine with your workspace API token
client = VigilClient(
    api_key=os.getenv("VIGIL_API_KEY"),
    endpoint="https://api.vigil.security/v1"
)

# Trigger deterministic AST review on pull request
review = client.reviews.create(
    repo="acme-corp/api-gateway",
    git_ref="refs/pull/104/head",
    strict_mode=True
)
print(f"Vigil Review Queued: {review.run_id}")`,
    node: `import { VigilClient } from '@vigil/sdk';

// Initialize the TypeScript Vigil Client
const client = new VigilClient({
  apiKey: process.env.VIGIL_API_KEY!,
  endpoint: 'https://api.vigil.security/v1',
});

// Run continuous code review gate
const result = await client.reviews.submit({
  target: './src',
  taintPropagation: true,
  zeroExecution: true,
});
console.log('Findings detected:', result.total_findings);`,
    curl: `curl -X POST https://api.vigil.security/v1/reviews \\
  -H "Authorization: Bearer $VIGIL_API_KEY" \\
  -H "Content-Type: application/json" \\
  -H "X-Idempotency-Key: $(uuidgen)" \\
  -d '{
    "language": "python",
    "policy_profile": "strict_owasp",
    "git_context": {
      "repo": "acme/auth-service",
      "commit": "HEAD"
    }
  }'`,
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(codeSnippets[framework]);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) return;
    setSubmitted(true);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-in fade-in duration-200">
      <div
        ref={modalRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="get-started-title"
        aria-describedby="get-started-desc"
        className="relative w-full max-w-2xl bg-[#09090b] border border-white/15 rounded-xl shadow-2xl overflow-hidden flex flex-col"
      >
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/10 bg-white/[0.02]">
          <div className="flex items-center gap-2.5">
            <div className="w-2 h-2 rounded-full bg-white animate-pulse" />
            <h2 id="get-started-title" className="text-sm font-semibold tracking-wide text-white uppercase font-mono">
              Get Started with Vigil Security
            </h2>
          </div>
          <button
            onClick={onClose}
            className={`text-white/40 hover:text-white transition-colors p-1 rounded-md hover:bg-white/5 ${focusRing}`}
            aria-label="Close modal"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div id="get-started-desc" className="p-6 space-y-5">
          {submitted ? (
            <div className="py-8 text-center space-y-3">
              <div className="w-12 h-12 rounded-full bg-white/10 border border-white/20 flex items-center justify-center mx-auto text-white">
                <Check className="w-6 h-6" />
              </div>
              <h3 className="text-lg font-semibold text-white">API Access Initialized</h3>
              <p className="text-sm text-white/60 max-w-sm mx-auto">
                We have registered your workspace for early access. Use the sample code below to verify your webhook or SDK integration.
              </p>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="flex gap-2">
              <input
                id="api-email-input"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Enter engineering email for API credentials..."
                aria-label="Engineering email"
                className={`flex-1 bg-black border border-white/20 rounded-full px-4 py-2.5 text-xs text-white placeholder:text-white/40 focus:outline-none focus:border-white transition-colors ${focusRing}`}
              />
              <button
                type="submit"
                className={`px-5 py-2.5 rounded-full bg-white text-black text-xs font-bold uppercase tracking-wider hover:bg-white/90 transition-all cursor-pointer whitespace-nowrap ${focusRing}`}
              >
                Claim Sandbox Key
              </button>
            </form>
          )}

          {/* Language Selector */}
          <div>
            <div className="flex items-center justify-between pb-2">
              <div className="flex items-center gap-1.5 text-xs text-white/50 font-mono uppercase tracking-wider">
                <Terminal className="w-3.5 h-3.5" />
                <span>Quickstart SDK</span>
              </div>
              <div className="flex rounded-md bg-white/5 p-0.5 border border-white/10 text-[11px] font-mono">
                <button
                  onClick={() => setFramework('python')}
                  className={`px-3 py-1 rounded transition-colors ${focusRing} ${
                    framework === 'python' ? 'bg-white text-black font-semibold' : 'text-white/60 hover:text-white'
                  }`}
                >
                  Python
                </button>
                <button
                  onClick={() => setFramework('node')}
                  className={`px-3 py-1 rounded transition-colors ${focusRing} ${
                    framework === 'node' ? 'bg-white text-black font-semibold' : 'text-white/60 hover:text-white'
                  }`}
                >
                  TypeScript
                </button>
                <button
                  onClick={() => setFramework('curl')}
                  className={`px-3 py-1 rounded transition-colors ${focusRing} ${
                    framework === 'curl' ? 'bg-white text-black font-semibold' : 'text-white/60 hover:text-white'
                  }`}
                >
                  cURL
                </button>
              </div>
            </div>

            <div className="relative rounded-lg bg-black border border-white/15 overflow-hidden">
              <pre className="p-4 font-mono text-xs text-white/80 overflow-x-auto leading-relaxed max-h-56">
                <code>{codeSnippets[framework]}</code>
              </pre>
              <button
                onClick={handleCopy}
                aria-label={copied ? 'Copied code to clipboard' : 'Copy code snippet'}
                className={`absolute top-2.5 right-2.5 flex items-center gap-1 px-2.5 py-1 rounded bg-white/10 hover:bg-white/20 border border-white/10 text-[10px] font-mono text-white transition-colors cursor-pointer ${focusRing}`}
              >
                {copied ? (
                  <>
                    <Check className="w-3 h-3 text-emerald-400" />
                    <span>Copied</span>
                  </>
                ) : (
                  <>
                    <Copy className="w-3 h-3" />
                    <span>Copy</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-white/10 bg-black/50 flex items-center justify-between text-xs text-white/40">
          <span>Production Ready • End-to-end Encrypted • SOC2 Type II Compliant</span>
          <button
            onClick={onClose}
            className={`text-white hover:text-white/80 font-medium tracking-wide transition-colors px-2 py-1 rounded ${focusRing}`}
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
};
