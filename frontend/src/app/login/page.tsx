'use client';

import React, { useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/context/AuthContext';
import { ShieldCheck, Lock, Mail, ArrowRight, AlertCircle } from 'lucide-react';

import { focusRing } from '@/lib/styles';

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const returnUrl = searchParams.get('redirect') || '/dashboard';

  const { login, isLoading } = useAuth();
  const [email, setEmail] = useState('sec-lead@vigil.internal');
  const [password, setPassword] = useState('enterprise-secret');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      await login(email, password);
      router.push(returnUrl);
    } catch (err: unknown) {
      const errorMsg =
        err instanceof Error
          ? err.message
          : 'Authentication failed. Please check your credentials.';
      setError(errorMsg);
    } finally {
      setSubmitting(false);
    }
  };

  const fillTestCredentials = (testEmail: string) => {
    setEmail(testEmail);
    setPassword('enterprise-secret');
    setError(null);
  };

  return (
    <div className="w-full max-w-md p-8 rounded-2xl border border-white/15 bg-[#09090b] shadow-[0_0_80px_rgba(0,0,0,0.8)]">
      {/* Header */}
      <div className="flex flex-col items-center text-center mb-8">
        <Link href="/" className={`flex items-center gap-2 mb-4 group p-1 rounded ${focusRing}`}>
          <img
            src="/images/vigil-logo.png"
            alt="Vigil Security Logo"
            className="h-8 w-auto transition-transform group-hover:scale-105"
          />
        </Link>
        <h1 className="text-xl font-medium tracking-tight text-white">
          SecOps Console Authentication
        </h1>
        <p className="text-xs text-white/50 mt-1">
          Zero-execution static safety & multi-agent telemetry access
        </p>
      </div>

      {/* Error notification */}
      {error && (
        <div
          role="alert"
          aria-live="assertive"
          className="mb-6 p-3 rounded-xl border border-rose-500/30 bg-rose-500/10 text-rose-300 text-xs flex items-start gap-2.5"
        >
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      {/* Credentials form */}
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="work-email" className="block text-xs font-mono uppercase tracking-wider text-white/60 mb-1.5">
            Work Email
          </label>
          <div className="relative">
            <Mail className="absolute left-3 top-2.5 w-4 h-4 text-white/40" />
            <input
              id="work-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className={`w-full pl-9 pr-3 py-2 bg-white/[0.04] border border-white/10 rounded-xl text-xs text-white placeholder-white/30 transition-all font-mono ${focusRing}`}
              placeholder="analyst@enterprise.com"
            />
          </div>
        </div>

        <div>
          <label htmlFor="work-password" className="block text-xs font-mono uppercase tracking-wider text-white/60 mb-1.5">
            Password or Token
          </label>
          <div className="relative">
            <Lock className="absolute left-3 top-2.5 w-4 h-4 text-white/40" />
            <input
              id="work-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className={`w-full pl-9 pr-3 py-2 bg-white/[0.04] border border-white/10 rounded-xl text-xs text-white placeholder-white/30 transition-all font-mono ${focusRing}`}
              placeholder="••••••••••••"
            />
          </div>
        </div>

        <button
          type="submit"
          disabled={submitting || isLoading}
          className={`w-full mt-2 py-2.5 bg-white hover:bg-zinc-200 text-black font-semibold text-xs rounded-xl flex items-center justify-center gap-2 transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed shadow-md ${focusRing}`}
        >
          <span>{submitting ? 'Authenticating...' : 'Sign In to Console'}</span>
          <ArrowRight className="w-3.5 h-3.5" />
        </button>
      </form>

      {/* Quick Test Credential Autofill */}
      <div className="mt-8 pt-6 border-t border-white/10">
        <div className="text-[11px] font-mono text-white/40 uppercase mb-2.5">
          Quick Preset Test Accounts:
        </div>
        <div className="grid grid-cols-2 gap-2">
          <button
            type="button"
            onClick={() => fillTestCredentials('sec-lead@vigil.internal')}
            className={`px-2.5 py-1.5 rounded-lg border border-white/10 bg-white/[0.02] hover:bg-white/[0.06] text-[11px] text-zinc-300 font-mono text-left transition-colors cursor-pointer ${focusRing}`}
          >
            Lead Reviewer
          </button>
          <button
            type="button"
            onClick={() => fillTestCredentials('admin@vigil.sec')}
            className={`px-2.5 py-1.5 rounded-lg border border-white/10 bg-white/[0.02] hover:bg-white/[0.06] text-[11px] text-zinc-300 font-mono text-left transition-colors cursor-pointer ${focusRing}`}
          >
            SecOps Admin
          </button>
        </div>
      </div>

      {/* Compliance footer */}
      <div className="mt-6 flex items-center justify-center gap-1.5 text-[11px] font-mono text-white/40">
        <ShieldCheck className="w-3.5 h-3.5 text-white/60" />
        <span>TLS 1.3 / Zero-Execution Ephemeral Memory Session</span>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <main className="min-h-screen bg-black text-white flex items-center justify-center p-4">
      <Suspense
        fallback={
          <div className="w-full max-w-md p-8 rounded-2xl border border-white/10 bg-[#09090b] text-center text-xs font-mono text-white/50">
            Initializing secure authentication channel...
          </div>
        }
      >
        <LoginForm />
      </Suspense>
    </main>
  );
}
