'use client';

import React, { useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { ShieldCheck, Lock, Mail, Building2, ArrowRight, AlertCircle, CheckCircle2 } from 'lucide-react';

import { api } from '@/lib/api';
import { focusRing } from '@/lib/styles';

interface FieldErrors {
  org?: string;
  email?: string;
  password?: string;
  confirmPassword?: string;
}

function RegisterForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const returnUrl = searchParams.get('redirect') || '/dashboard';

  const [org, setOrg] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');

  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [globalError, setGlobalError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string>('');

  const validateClientSide = (): boolean => {
    const errors: FieldErrors = {};

    if (!org.trim()) {
      errors.org = 'Organization name is required.';
    } else if (org.trim().length < 2) {
      errors.org = 'Organization name must be at least 2 characters.';
    }

    if (!email.trim()) {
      errors.email = 'Email address is required.';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      errors.email = 'Please enter a valid email address.';
    }

    if (!password) {
      errors.password = 'Password is required.';
    } else if (password.length < 12) {
      errors.password = 'Password must be at least 12 characters.';
    } else if (!/[A-Za-z]/.test(password) || !/\d/.test(password)) {
      errors.password = 'Password must contain at least one letter and one number.';
    }

    if (!confirmPassword) {
      errors.confirmPassword = 'Confirmation password is required.';
    } else if (password !== confirmPassword) {
      errors.confirmPassword = 'Passwords do not match.';
    }

    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setGlobalError(null);

    if (!validateClientSide()) {
      return;
    }

    setSubmitting(true);
    setStatusMessage('Creating enterprise security tenant...');

    try {
      const response = await api.register({
        email: email.trim(),
        password,
        organization_name: org.trim(),
      });

      setStatusMessage('Registration successful! Launching workspace...');

      // Store issued JWT token in localStorage per architecture
      if (typeof window !== 'undefined' && response.access_token) {
        localStorage.setItem('vigil_token', response.access_token);
      }

      router.push(returnUrl);
    } catch (err: unknown) {
      setStatusMessage('');
      const status = (err as { status?: number })?.status;
      const errorResponse = (err as { errorResponse?: { detail?: { code?: string; message?: string } | Array<{ msg?: string; loc?: string[] }> } })?.errorResponse;

      if (status === 409 || (errorResponse?.detail && 'code' in errorResponse.detail && errorResponse.detail.code === 'email_taken')) {
        setFieldErrors((prev) => ({ ...prev, email: 'Email already registered' }));
        setGlobalError('An account with this email address already exists. Please sign in instead.');
      } else if (status === 429) {
        setGlobalError('Too many attempts. Try again later.');
      } else if (status === 422 && Array.isArray(errorResponse?.detail)) {
        const detailArray = errorResponse.detail;
        const mappedErrors: FieldErrors = {};
        for (const item of detailArray) {
          const field = item.loc?.[item.loc.length - 1];
          if (field === 'organization_name') mappedErrors.org = item.msg || 'Invalid organization name';
          else if (field === 'email') mappedErrors.email = item.msg || 'Invalid email address';
          else if (field === 'password') mappedErrors.password = item.msg || 'Invalid password';
        }
        setFieldErrors(mappedErrors);
        setGlobalError('Please resolve the validation errors below.');
      } else {
        const message = err instanceof Error ? err.message : 'Registration failed. Please try again.';
        setGlobalError(message);
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="w-full max-w-md p-8 rounded-2xl border border-white/15 bg-[#09090b] shadow-[0_0_80px_rgba(0,0,0,0.8)]">
      {/* Header */}
      <div className="flex flex-col items-center text-center mb-8">
        <Link href="/" className={`flex items-center gap-2 mb-4 group p-1 rounded ${focusRing}`} aria-label="Return to Vigil home">
          <img
            src="/images/vigil-logo.png"
            alt="Vigil Security Logo"
            className="h-8 w-auto transition-transform group-hover:scale-105"
          />
        </Link>
        <h1 className="text-xl font-medium tracking-tight text-white">
          Create your Vigil account
        </h1>
        <p className="text-xs text-white/50 mt-1">
          Isolated tenant provisioning with zero-data-retention security
        </p>
      </div>

      {/* Global Error Banner */}
      {globalError && (
        <div
          role="alert"
          aria-live="assertive"
          className="mb-6 p-3 rounded-xl border border-rose-500/30 bg-rose-500/10 text-rose-300 text-xs flex items-start gap-2.5"
        >
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
          <span>{globalError}</span>
        </div>
      )}

      {/* Live Accessibility Status Announcement */}
      <div className="sr-only" role="status" aria-live="polite">
        {statusMessage}
      </div>

      {/* Registration Form */}
      <form onSubmit={handleSubmit} className="space-y-4" noValidate>
        {/* Organization Name Field */}
        <div>
          <label htmlFor="org" className="block text-xs font-mono uppercase tracking-wider text-white/60 mb-1.5">
            Organization Name
          </label>
          <div className="relative">
            <Building2 className="absolute left-3 top-2.5 w-4 h-4 text-white/40" />
            <input
              id="org"
              type="text"
              value={org}
              onChange={(e) => {
                setOrg(e.target.value);
                if (fieldErrors.org) setFieldErrors((prev) => ({ ...prev, org: undefined }));
              }}
              required
              aria-required="true"
              aria-invalid={Boolean(fieldErrors.org)}
              aria-describedby={fieldErrors.org ? 'org-error' : undefined}
              className={`w-full pl-9 pr-3 py-2 bg-white/[0.04] border ${fieldErrors.org ? 'border-rose-500/60' : 'border-white/10'} rounded-xl text-xs text-white placeholder-white/30 transition-all font-mono ${focusRing}`}
              placeholder="Acme Security Inc."
            />
          </div>
          {fieldErrors.org && (
            <p id="org-error" role="alert" className="mt-1 text-[11px] text-rose-400 font-mono">
              {fieldErrors.org}
            </p>
          )}
        </div>

        {/* Work Email Field */}
        <div>
          <label htmlFor="email" className="block text-xs font-mono uppercase tracking-wider text-white/60 mb-1.5">
            Work Email
          </label>
          <div className="relative">
            <Mail className="absolute left-3 top-2.5 w-4 h-4 text-white/40" />
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => {
                setEmail(e.target.value);
                if (fieldErrors.email) setFieldErrors((prev) => ({ ...prev, email: undefined }));
              }}
              required
              aria-required="true"
              aria-invalid={Boolean(fieldErrors.email)}
              aria-describedby={fieldErrors.email ? 'email-error' : undefined}
              className={`w-full pl-9 pr-3 py-2 bg-white/[0.04] border ${fieldErrors.email ? 'border-rose-500/60' : 'border-white/10'} rounded-xl text-xs text-white placeholder-white/30 transition-all font-mono ${focusRing}`}
              placeholder="analyst@enterprise.com"
            />
          </div>
          {fieldErrors.email && (
            <p id="email-error" role="alert" className="mt-1 text-[11px] text-rose-400 font-mono">
              {fieldErrors.email}
            </p>
          )}
        </div>

        {/* Password Field */}
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <label htmlFor="password" className="block text-xs font-mono uppercase tracking-wider text-white/60">
              Password
            </label>
            <span className="text-[10px] text-white/40 font-mono">Min 12 chars (letter + number)</span>
          </div>
          <div className="relative">
            <Lock className="absolute left-3 top-2.5 w-4 h-4 text-white/40" />
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => {
                setPassword(e.target.value);
                if (fieldErrors.password) setFieldErrors((prev) => ({ ...prev, password: undefined }));
              }}
              required
              aria-required="true"
              aria-invalid={Boolean(fieldErrors.password)}
              aria-describedby={fieldErrors.password ? 'password-error' : undefined}
              className={`w-full pl-9 pr-3 py-2 bg-white/[0.04] border ${fieldErrors.password ? 'border-rose-500/60' : 'border-white/10'} rounded-xl text-xs text-white placeholder-white/30 transition-all font-mono ${focusRing}`}
              placeholder="••••••••••••"
            />
          </div>
          {fieldErrors.password && (
            <p id="password-error" role="alert" className="mt-1 text-[11px] text-rose-400 font-mono">
              {fieldErrors.password}
            </p>
          )}
        </div>

        {/* Confirm Password Field */}
        <div>
          <label htmlFor="confirm-password" className="block text-xs font-mono uppercase tracking-wider text-white/60 mb-1.5">
            Confirm Password
          </label>
          <div className="relative">
            <Lock className="absolute left-3 top-2.5 w-4 h-4 text-white/40" />
            <input
              id="confirm-password"
              type="password"
              value={confirmPassword}
              onChange={(e) => {
                setConfirmPassword(e.target.value);
                if (fieldErrors.confirmPassword) setFieldErrors((prev) => ({ ...prev, confirmPassword: undefined }));
              }}
              required
              aria-required="true"
              aria-invalid={Boolean(fieldErrors.confirmPassword)}
              aria-describedby={fieldErrors.confirmPassword ? 'confirm-password-error' : undefined}
              className={`w-full pl-9 pr-3 py-2 bg-white/[0.04] border ${fieldErrors.confirmPassword ? 'border-rose-500/60' : 'border-white/10'} rounded-xl text-xs text-white placeholder-white/30 transition-all font-mono ${focusRing}`}
              placeholder="••••••••••••"
            />
          </div>
          {fieldErrors.confirmPassword && (
            <p id="confirm-password-error" role="alert" className="mt-1 text-[11px] text-rose-400 font-mono">
              {fieldErrors.confirmPassword}
            </p>
          )}
        </div>

        {/* Submit Button */}
        <button
          type="submit"
          disabled={submitting}
          className={`w-full mt-3 py-2.5 bg-white hover:bg-zinc-200 text-black font-semibold text-xs rounded-xl flex items-center justify-center gap-2 transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed shadow-md ${focusRing}`}
        >
          <span>{submitting ? 'Creating account...' : 'Create account'}</span>
          <ArrowRight className="w-3.5 h-3.5" />
        </button>
      </form>

      {/* Switch to Login */}
      <div className="mt-6 text-center text-xs text-white/50 font-mono">
        Already have an account?{' '}
        <Link
          href={`/login${returnUrl !== '/dashboard' ? `?redirect=${encodeURIComponent(returnUrl)}` : ''}`}
          className={`text-white hover:underline ${focusRing} p-0.5 rounded`}
        >
          Sign in
        </Link>
      </div>

      {/* Security disclosures */}
      <div className="mt-8 pt-6 border-t border-white/10 flex items-center justify-center gap-1.5 text-[11px] font-mono text-white/40">
        <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
        <span>Enterprise GDPR Compliance / Zero Data Retention</span>
      </div>
    </div>
  );
}

export default function RegisterPage() {
  return (
    <main className="min-h-screen bg-black text-white flex items-center justify-center p-4">
      <Suspense
        fallback={
          <div className="w-full max-w-md p-8 rounded-2xl border border-white/10 bg-[#09090b] text-center text-xs font-mono text-white/50">
            Initializing secure registration channel...
          </div>
        }
      >
        <RegisterForm />
      </Suspense>
    </main>
  );
}
