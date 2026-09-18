'use client';

import { useState } from 'react';
import styles from './LoginForm.module.css';
import { login } from '../lib/api';
import { setToken } from '../lib/token';

interface Props {
  onSuccess: () => void;
}

export default function LoginForm({ onSuccess }: Props) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const resp = await login(email, password);
      setToken(resp.access_token);
      onSuccess();
    } catch (err: any) {
      setError(err.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={styles.wrapper}>
      <div className="card fade-in" style={{ padding: '2rem', maxWidth: 420, width: '100%' }}>
        {/* Logo */}
        <div className={styles.logo}>
          <svg width="36" height="36" viewBox="0 0 36 36" fill="none" aria-hidden="true">
            <circle cx="18" cy="18" r="18" fill="rgba(245,158,11,0.12)" />
            <path d="M18 8L26 14v8l-8 6-8-6v-8L18 8z" stroke="#f59e0b" strokeWidth="1.5" fill="none" />
            <circle cx="18" cy="18" r="3" fill="#f59e0b" />
          </svg>
          <span>Vigil</span>
        </div>

        <h1 style={{ fontSize: '1.5rem', marginBottom: '0.25rem' }}>Sign in</h1>
        <p className="text-secondary" style={{ fontSize: '0.875rem', marginBottom: '1.5rem' }}>
          Phase 1 prototype — local auth only
        </p>

        <form onSubmit={handleSubmit} aria-label="Login form">
          <div className={styles.field}>
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              required
              autoComplete="email"
              placeholder="you@example.com"
            />
          </div>

          <div className={styles.field}>
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
              autoComplete="current-password"
              placeholder="••••••••"
            />
          </div>

          {error && (
            <p role="alert" className={styles.error}>{error}</p>
          )}

          <button
            id="login-submit"
            type="submit"
            className="btn btn-primary"
            style={{ width: '100%', justifyContent: 'center', marginTop: '1rem' }}
            disabled={loading}
            aria-busy={loading}
          >
            {loading ? <><span className="spinner" aria-hidden="true" /> Signing in…</> : 'Sign in'}
          </button>
        </form>

        <p className={styles.note}>
          🔒 Submitted code is <strong>never executed</strong> — static analysis only.
        </p>
      </div>
    </div>
  );
}
