'use client';

import { useState } from 'react';
import styles from './CodeEditor.module.css';
import { createReview, pollReview, grantConsent } from '../lib/api';
import type { ReviewRun } from '../lib/api';

interface Props {
  token: string;
  onResult: (run: ReviewRun) => void;
  onError: (msg: string) => void;
}

const LANGUAGES = ['python', 'javascript', 'typescript'] as const;
type Language = typeof LANGUAGES[number];

const PLACEHOLDERS: Record<Language, string> = {
  python: `# Paste Python code here…\nimport hashlib\n\ndef hash_password(pw: str) -> str:\n    # This is weak — Vigil will flag it\n    return hashlib.md5(pw.encode()).hexdigest()\n`,
  javascript: `// Paste JavaScript code here…\nconst cmd = userInput;\nrequire('child_process').exec(cmd); // Vigil will flag this\n`,
  typescript: `// Paste TypeScript code here…\nconst result = eval(userCode); // Vigil will flag this\n`,
};

export default function CodeEditor({ token, onResult, onError }: Props) {
  const [language, setLanguage] = useState<Language>('python');
  const [source, setSource] = useState('');
  const [loading, setLoading] = useState(false);
  const [statusMsg, setStatusMsg] = useState('');
  const [consentNeeded, setConsentNeeded] = useState(false);
  const [consentLoading, setConsentLoading] = useState(false);

  const sizeKB = (new TextEncoder().encode(source).byteLength / 1024).toFixed(1);
  const isOverLimit = new TextEncoder().encode(source).byteLength > 250 * 1024;

  async function handleGrantConsent() {
    setConsentLoading(true);
    try {
      await grantConsent(token, '1.0', true);
      setConsentNeeded(false);
      await handleSubmit();
    } catch (e: any) {
      onError(e.message);
    } finally {
      setConsentLoading(false);
    }
  }

  async function handleSubmit(e?: React.FormEvent) {
    e?.preventDefault();
    if (!source.trim()) { onError('Please paste or type some source code.'); return; }
    if (isOverLimit) { onError('File exceeds 250 KB limit.'); return; }

    setLoading(true);
    setStatusMsg('Submitting…');
    try {
      const { run_id } = await createReview(token, language, source);
      setStatusMsg('Analysing… (polling for results)');
      const run = await pollReview(token, run_id);
      onResult(run);
    } catch (err: any) {
      if (err.message === 'CONSENT_REQUIRED') {
        setConsentNeeded(true);
        setStatusMsg('');
      } else {
        onError(err.message);
      }
    } finally {
      setLoading(false);
      if (!consentNeeded) setStatusMsg('');
    }
  }

  return (
    <div className={styles.wrapper}>
      {/* Header bar */}
      <div className={styles.header}>
        <div className={styles.langTabs} role="tablist" aria-label="Select language">
          {LANGUAGES.map(l => (
            <button
              key={l}
              role="tab"
              aria-selected={language === l}
              id={`lang-tab-${l}`}
              className={`${styles.langTab} ${language === l ? styles.active : ''}`}
              onClick={() => setLanguage(l)}
              disabled={loading}
            >
              {l}
            </button>
          ))}
        </div>
        <span className={`${styles.sizeHint} ${isOverLimit ? styles.overLimit : ''}`}>
          {sizeKB} KB / 250 KB
        </span>
      </div>

      {/* Text area */}
      <form onSubmit={handleSubmit} aria-label="Code submission form">
        <textarea
          id="source-editor"
          aria-label="Source code input"
          className={styles.editor}
          value={source}
          onChange={e => setSource(e.target.value)}
          placeholder={PLACEHOLDERS[language]}
          spellCheck={false}
          disabled={loading}
        />

        {/* Consent gate */}
        {consentNeeded && (
          <div className={styles.consentBanner} role="alert">
            <span>⚖️</span>
            <div>
              <strong>Consent required</strong>
              <p>
                By proceeding you consent to your code being processed by Vigil
                for security analysis (Policy v1.0). No code is executed.
              </p>
            </div>
            <button
              id="grant-consent-btn"
              type="button"
              className="btn btn-primary"
              onClick={handleGrantConsent}
              disabled={consentLoading}
              aria-busy={consentLoading}
            >
              {consentLoading ? <span className="spinner" /> : 'I consent — Analyse'}
            </button>
          </div>
        )}

        <div className={styles.footer}>
          <p className={styles.hint}>
            🔒 Code is <strong>never executed</strong> — static analysis only
          </p>
          <button
            id="analyse-btn"
            type="submit"
            className="btn btn-primary"
            disabled={loading || isOverLimit || consentNeeded}
            aria-busy={loading}
          >
            {loading
              ? <><span className="spinner" aria-hidden="true" /> {statusMsg}</>
              : '▶ Analyse'}
          </button>
        </div>
      </form>
    </div>
  );
}
