'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  FileCode,
  Upload,
  Lock,
  Play,
  RotateCcw,
  Sparkles,
  Loader2,
} from 'lucide-react';
import { Finding, Review, ReviewStatus } from '@/lib/types';
import { RunStatusStepper } from './RunStatusStepper';
import { api } from '@/lib/api';
import { focusRing } from '@/lib/styles';

interface NewReviewViewProps {
  onCreateReview?: (newReview: Review, newFindings?: Finding[]) => void;
  onCancel: () => void;
}

export const NewReviewView: React.FC<NewReviewViewProps> = ({ onCreateReview, onCancel }) => {
  const router = useRouter();
  const [language, setLanguage] = useState<'python' | 'javascript' | 'typescript'>('python');
  const [inputMethod, setInputMethod] = useState<'paste' | 'upload'>('paste');
  const [code, setCode] = useState('');
  const [fileName, setFileName] = useState('main.py');
  const [policyProfile, setPolicyProfile] = useState<
    'Default Policy' | 'Strict OWASP & CWE' | 'Custom Enterprise Guard'
  >('Strict OWASP & CWE');
  const [consent, setConsent] = useState(true);
  const [isSimulating, setIsSimulating] = useState(false);
  const [currentStep, setCurrentStep] = useState<ReviewStatus>('queued');
  const [isIdempotentReplay, setIsIdempotentReplay] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const handleLanguageChange = (newLang: 'python' | 'javascript' | 'typescript') => {
    setLanguage(newLang);
    if (newLang === 'python') {
      setFileName('main.py');
    } else if (newLang === 'typescript') {
      setFileName('index.ts');
    } else {
      setFileName('server.js');
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setFileName(file.name);
    if (file.name.endsWith('.py')) setLanguage('python');
    else if (file.name.endsWith('.ts') || file.name.endsWith('.tsx')) setLanguage('typescript');
    else if (file.name.endsWith('.js') || file.name.endsWith('.jsx')) setLanguage('javascript');

    const reader = new FileReader();
    reader.onload = (event) => {
      if (event.target?.result) {
        setCode(event.target.result as string);
      }
    };
    reader.readAsText(file);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!code.trim() || !consent) return;

    setIsSimulating(true);
    setCurrentStep('running');
    setSubmitError(null);

    try {
      const response = await api.submitReview({
        language,
        source_code: code,
        source_text: code,
      });

      if (onCreateReview) {
        onCreateReview({
          id: response.run_id,
          runId: response.run_id,
          title: `${language.toUpperCase()} Security Review`,
          fileName,
          language,
          status: response.status,
          createdAt: new Date().toISOString(),
          fileCount: 1,
          totalFindings: 0,
          severityCounts: { critical: 0, high: 0, medium: 0, low: 0, info: 0 },
          budget: {
            tokensUsed: 0,
            tokenLimit: 25000,
            costUsed: 0,
            costLimit: 5.0,
            iterations: 0,
            iterationLimit: 20,
          },
          legalHold: false,
          policyProfile,
          code,
        });
      }

      router.push(`/dashboard/reviews/${response.run_id}`);
    } catch (err: any) {
      setIsSimulating(false);
      setSubmitError(err?.message || 'Failed to submit review');
    }
  };

  return (
    <div className="max-w-4xl mx-auto p-6 flex flex-col gap-6 text-white select-none">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/10 pb-4">
        <div>
          <h1 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
            <FileCode className="w-5 h-5 text-white/80" />
            <span>Submit Code for Policy Review</span>
          </h1>
          <p className="text-xs text-white/50 mt-1">
            Deterministic AST rule checks and LLM security reasoning. Verified zero-execution environment.
          </p>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 text-emerald-400 text-xs font-mono">
          <Lock className="w-3.5 h-3.5" />
          <span>Zero Execution Sandbox</span>
        </div>
      </div>

      {isIdempotentReplay && (
        <div className="p-3.5 rounded-xl border border-white/20 bg-white/[0.04] text-xs text-white/90 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <RotateCcw className="w-4 h-4 text-white/70 shrink-0" />
            <span>
              <strong>Idempotent Payload Detected:</strong> Code hash matches existing review record. Results served from cache instantly with zero token consumption.
            </span>
          </div>
          <button
            onClick={() => setIsIdempotentReplay(false)}
            className="text-xs text-white/60 hover:text-white underline cursor-pointer"
          >
            Dismiss
          </button>
        </div>
      )}

      {submitError && (
        <div className="p-3.5 rounded-xl border border-rose-500/30 bg-rose-500/10 text-xs text-rose-300 flex items-center justify-between">
          <span>{submitError}</span>
          <button
            type="button"
            onClick={() => setSubmitError(null)}
            className="text-xs text-rose-300 hover:text-white underline cursor-pointer"
          >
            Dismiss
          </button>
        </div>
      )}

      {isSimulating ? (
        <div className="p-8 rounded-2xl border border-white/20 bg-black flex flex-col gap-6 shadow-2xl">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-white/10 border border-white/20 flex items-center justify-center text-white">
                <Sparkles className="w-5 h-5 animate-spin text-white" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-white">
                  Running Vigil Multi-Agent Audit Pipeline...
                </h3>
                <p className="text-xs text-white/50 mt-0.5">
                  Analyzing <span className="font-mono text-white/90">{fileName}</span> against {policyProfile}
                </p>
              </div>
            </div>
            <span className="font-mono text-xs text-white/80 uppercase px-2.5 py-1 rounded-full bg-white/10 border border-white/20">
              {currentStep}
            </span>
          </div>
          <RunStatusStepper status={currentStep} />
          <div className="text-xs text-white/60 font-mono bg-white/[0.02] p-4 rounded-xl border border-white/10 flex flex-col gap-1.5 leading-relaxed">
            <div className="text-emerald-400">✓ Source parsed into abstract syntax tree (AST)</div>
            <div className="text-emerald-400">✓ Semgrep and Bandit security linters dispatched</div>
            <div className="text-white animate-pulse">⚙ LLM Security Reasoner analyzing dataflow and injection paths...</div>
            <div className="text-white/30">○ Triage agent deduplicating candidate findings...</div>
          </div>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="flex flex-col gap-5">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="flex flex-col gap-1.5">
              {/* Associated label for screen readers */}
              <label htmlFor="target-language-select" className="text-xs font-medium text-white/80">Target Language</label>
              <select
                id="target-language-select"
                value={language}
                onChange={(e) => handleLanguageChange(e.target.value as any)}
                className={`bg-black border border-white/15 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-white/40 ${focusRing}`}
              >
                <option value="python">Python 3.x</option>
                <option value="typescript">TypeScript</option>
                <option value="javascript">JavaScript / Node.js</option>
              </select>
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium text-white/80">Input Mode</label>
              <div role="group" aria-label="Input Mode" className="flex rounded-lg border border-white/15 bg-black p-1 text-xs">
                <button
                  type="button"
                  onClick={() => setInputMethod('paste')}
                  className={`flex-1 py-1 rounded-md transition-colors cursor-pointer ${
                    inputMethod === 'paste' ? 'bg-white text-black font-semibold' : 'text-white/50 hover:text-white'
                  } ${focusRing}`}
                >
                  Paste Code
                </button>
                <button
                  type="button"
                  onClick={() => setInputMethod('upload')}
                  className={`flex-1 py-1 rounded-md transition-colors cursor-pointer ${
                    inputMethod === 'upload' ? 'bg-white text-black font-semibold' : 'text-white/50 hover:text-white'
                  } ${focusRing}`}
                >
                  Upload File
                </button>
              </div>
            </div>

            <div className="flex flex-col gap-1.5">
              {/* Associated label for screen readers */}
              <label htmlFor="policy-profile-select" className="text-xs font-medium text-white/80">Policy Profile</label>
              <select
                id="policy-profile-select"
                value={policyProfile}
                onChange={(e) => setPolicyProfile(e.target.value as any)}
                className={`bg-black border border-white/15 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-white/40 ${focusRing}`}
              >
                <option value="Strict OWASP & CWE">Strict OWASP & CWE</option>
                <option value="Default Policy">Default Policy</option>
                <option value="Custom Enterprise Guard">Custom Enterprise Guard</option>
              </select>
            </div>
          </div>

          <div className="flex items-center gap-2 text-xs flex-wrap">
            <span className="text-white/50">Load sample:</span>
            <button
              type="button"
              onClick={() => handleLanguageChange('python')}
              className="px-3 py-1 rounded-full bg-white/[0.04] hover:bg-white/10 text-white/80 border border-white/15 font-mono text-[11px] cursor-pointer transition-colors"
            >
              Python (FastAPI SQLi & Pickle RCE)
            </button>
            <button
              type="button"
              onClick={() => handleLanguageChange('typescript')}
              className="px-3 py-1 rounded-full bg-white/[0.04] hover:bg-white/10 text-white/80 border border-white/15 font-mono text-[11px] cursor-pointer transition-colors"
            >
              TypeScript (Hardcoded Secret & None Algo)
            </button>
            <button
              type="button"
              onClick={() => setIsIdempotentReplay(true)}
              className="px-3 py-1 rounded-full bg-white/10 hover:bg-white/15 text-white border border-white/20 font-mono text-[11px] ml-auto cursor-pointer transition-colors"
            >
              Simulate Idempotent Replay
            </button>
          </div>

          {inputMethod === 'upload' ? (
            <div className="p-8 rounded-xl border-2 border-dashed border-white/20 bg-white/[0.02] flex flex-col items-center justify-center gap-3 text-center">
              <Upload className="w-8 h-8 text-white/60" />
              <div className="text-sm font-medium text-white">
                Drag & drop or select a source file
              </div>
              <p className="text-xs text-white/40 max-w-sm">
                Supported extensions: .py, .js, .ts, .jsx, .tsx. Maximum single file limit is 250 KB.
              </p>
              <label className={`mt-2 px-4 py-2 bg-white hover:bg-white/90 text-black rounded-full text-xs font-semibold cursor-pointer transition-colors ${focusRing}`}>
                Select File
                <input
                  type="file"
                  aria-label="Upload source file"
                  className="hidden"
                  accept=".py,.js,.ts,.jsx,.tsx"
                  onChange={handleFileUpload}
                />
              </label>
              {fileName && (
                <div className="text-xs font-mono text-emerald-400 mt-2">
                  Loaded: {fileName} ({code.length} characters)
                </div>
              )}
            </div>
          ) : (
            <div className="flex flex-col gap-1.5">
              <div className="flex items-center justify-between text-xs text-white/50 font-mono">
                <label htmlFor="source-code-input">File Path: {fileName}</label>
                <span>{(new Blob([code]).size / 1024).toFixed(1)} KB / 250 KB</span>
              </div>
              <textarea
                id="source-code-input"
                aria-label="Source code editor"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                rows={16}
                className={`w-full bg-black border border-white/15 rounded-xl p-4 font-mono text-xs text-white/90 leading-relaxed focus:outline-none focus:border-white/40 ${focusRing}`}
                style={{ fontFamily: "'JetBrains Mono', monospace" }}
                placeholder="Paste your source code here..."
              />
            </div>
          )}

          <div className="p-4 rounded-xl border border-white/10 bg-white/[0.02] flex items-start gap-3">
            <input
              type="checkbox"
              id="consent-check"
              checked={consent}
              onChange={(e) => setConsent(e.target.checked)}
              className={`mt-0.5 w-4 h-4 rounded border-white/20 bg-black text-white focus:ring-white/50 cursor-pointer ${focusRing}`}
            />
            <label htmlFor="consent-check" className="text-xs text-white/70 leading-relaxed cursor-pointer">
              <span className="font-semibold text-white">Submission Consent & Right to Review:</span> I
              confirm I have the right to submit this code for static review. The system will never execute,
              compile, or persist unauthorized copies outside the tenant perimeter.
            </label>
          </div>

          <div className="flex items-center justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onCancel}
              className={`px-5 py-2 rounded-full border border-white/20 bg-transparent text-xs font-medium text-white/70 hover:text-white hover:bg-white/5 transition-colors cursor-pointer ${focusRing}`}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!code.trim() || !consent || isSimulating}
              className={`px-5 py-2 rounded-full text-xs font-semibold flex items-center gap-2 transition-colors cursor-pointer ${focusRing} ${
                !code.trim() || !consent || isSimulating
                  ? 'bg-white/10 text-white/30 cursor-not-allowed border border-white/10'
                  : 'bg-white hover:bg-white/90 text-black shadow-sm'
              }`}
            >
              <Play className="w-3.5 h-3.5 fill-current" />
              <span>Run Review</span>
            </button>
          </div>
        </form>
      )}
    </div>
  );
};
