'use client';

import React, { useState, useEffect } from 'react';

interface LearningConsentBannerProps {
  token: string;
  onConsentChanged?: (granted: boolean) => void;
}

export const LearningConsentBanner: React.FC<LearningConsentBannerProps> = ({
  token,
  onConsentChanged,
}) => {
  const [granted, setGranted] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(false);
  const [showConfirmModal, setShowConfirmModal] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  useEffect(() => {
    // Check initial consent status (default OFF per FR-109)
    async function checkStatus() {
      try {
        const res = await fetch(`${apiBase}/v1/consent/learning/status`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) {
          const data = await res.json();
          setGranted(Boolean(data.active && data.granted));
        }
      } catch (err) {
        // Fallback default off
        setGranted(false);
      }
    }
    if (token) {
      checkStatus();
    }
  }, [token, apiBase]);

  const updateConsent = async (grantState: boolean) => {
    setLoading(true);
    setError(null);
    setSuccessMessage(null);
    try {
      const res = await fetch(`${apiBase}/v1/consent/learning`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ granted: grantState }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail?.message || errData.message || 'Failed to update consent');
      }

      setGranted(grantState);
      if (onConsentChanged) {
        onConsentChanged(grantState);
      }
      setSuccessMessage(
        grantState
          ? 'Governed learning enabled: Dispositions will be indexed privately with zero code retention.'
          : 'Consent revoked: All tenant learning index data purged immediately.'
      );
    } catch (err: any) {
      setError(err.message || 'An error occurred while updating learning consent.');
    } finally {
      setLoading(false);
      setShowConfirmModal(false);
    }
  };

  const handleToggle = () => {
    if (granted) {
      // Show confirmation dialog before revoking and purging
      setShowConfirmModal(true);
    } else {
      updateConsent(true);
    }
  };

  return (
    <section
      aria-label="Governed Learning Consent Settings"
      style={{
        background: '#1e293b',
        border: '1px solid #334155',
        borderRadius: '8px',
        padding: '16px',
        color: '#f8fafc',
        marginBottom: '16px',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 600, color: '#e2e8f0' }}>
            Governed Learning Loop (FR-109)
          </h3>
          <p style={{ margin: '4px 0 0', fontSize: '0.875rem', color: '#94a3b8' }}>
            Allow anonymized feedback dispositions to train localized tenant triage models. Zero raw code is ever indexed. Default is strictly OFF.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span
            id="consent-status-label"
            style={{
              fontSize: '0.875rem',
              fontWeight: 500,
              color: granted ? '#4ade80' : '#94a3b8',
            }}
          >
            {granted ? 'Active (ON)' : 'Disabled (OFF)'}
          </span>
          <button
            type="button"
            role="switch"
            aria-checked={granted}
            aria-labelledby="consent-status-label"
            onClick={handleToggle}
            disabled={loading}
            style={{
              background: granted ? '#22c55e' : '#475569',
              color: '#ffffff',
              border: 'none',
              borderRadius: '20px',
              padding: '6px 16px',
              cursor: loading ? 'not-allowed' : 'pointer',
              fontWeight: 600,
              fontSize: '0.875rem',
              transition: 'background 0.2s ease',
            }}
          >
            {loading ? 'Updating...' : granted ? 'Disable Learning' : 'Enable Learning'}
          </button>
        </div>
      </div>

      {error && (
        <div
          role="alert"
          style={{
            marginTop: '12px',
            padding: '8px 12px',
            background: 'rgba(239, 68, 68, 0.1)',
            border: '1px solid #ef4444',
            borderRadius: '4px',
            color: '#fca5a5',
            fontSize: '0.875rem',
          }}
        >
          {error}
        </div>
      )}

      {successMessage && (
        <div
          role="status"
          style={{
            marginTop: '12px',
            padding: '8px 12px',
            background: 'rgba(34, 197, 94, 0.1)',
            border: '1px solid #22c55e',
            borderRadius: '4px',
            color: '#86efac',
            fontSize: '0.875rem',
          }}
        >
          {successMessage}
        </div>
      )}

      {showConfirmModal && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="revoke-modal-title"
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.7)',
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            zIndex: 9999,
          }}
        >
          <div
            style={{
              background: '#0f172a',
              border: '1px solid #334155',
              borderRadius: '8px',
              padding: '24px',
              maxWidth: '480px',
              width: '90%',
              color: '#f8fafc',
            }}
          >
            <h4 id="revoke-modal-title" style={{ margin: '0 0 12px', fontSize: '1.125rem' }}>
              Revoke Learning Consent & Purge Data?
            </h4>
            <p style={{ fontSize: '0.875rem', color: '#cbd5e1', lineHeight: 1.5 }}>
              Revoking consent immediately triggers a complete, synchronous purge of all historical disposition vectors from the tenant's RAG index (AC-109.6). Future triage will not use prior dispositions.
            </p>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '20px' }}>
              <button
                type="button"
                onClick={() => setShowConfirmModal(false)}
                disabled={loading}
                style={{
                  background: 'transparent',
                  border: '1px solid #64748b',
                  color: '#e2e8f0',
                  padding: '8px 16px',
                  borderRadius: '4px',
                  cursor: 'pointer',
                }}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => updateConsent(false)}
                disabled={loading}
                style={{
                  background: '#ef4444',
                  border: 'none',
                  color: '#ffffff',
                  padding: '8px 16px',
                  borderRadius: '4px',
                  fontWeight: 600,
                  cursor: loading ? 'not-allowed' : 'pointer',
                }}
              >
                {loading ? 'Purging...' : 'Confirm Revoke & Purge'}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
};
