'use client';

import React from 'react';
import { ShieldAlert, Trash2, X, Lock } from 'lucide-react';
import { useModalA11y } from '@/lib/useFocusTrap';
import { focusRing } from '@/lib/styles';

interface DeleteConfirmModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  reviewTitle: string;
  legalHold: boolean;
}

export const DeleteConfirmModal: React.FC<DeleteConfirmModalProps> = ({
  isOpen,
  onClose,
  onConfirm,
  reviewTitle,
  legalHold,
}) => {
  const modalRef = useModalA11y(isOpen, onClose);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in">
      <div
        ref={modalRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="delete-dialog-title"
        aria-describedby="delete-dialog-description"
        className="w-full max-w-md rounded-2xl border border-white/15 bg-black shadow-2xl p-6 text-white flex flex-col gap-4"
      >
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div
              className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                legalHold
                  ? 'bg-amber-500/15 text-amber-400 border border-amber-500/30'
                  : 'bg-rose-500/15 text-rose-400 border border-rose-500/30'
              }`}
            >
              {legalHold ? (
                <ShieldAlert className="w-5 h-5" />
              ) : (
                <Trash2 className="w-5 h-5" />
              )}
            </div>
            <div>
              <h3 id="delete-dialog-title" className="text-base font-semibold text-white">
                {legalHold ? 'Deletion Blocked by Policy' : 'Delete Code Review'}
              </h3>
              <p className="text-xs text-white/50 mt-0.5">
                Target: <span className="text-white font-mono">{reviewTitle}</span>
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label="Close modal"
            className={`text-white/40 hover:text-white p-1 rounded-full hover:bg-white/10 ${focusRing}`}
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {legalHold ? (
          <div
            id="delete-dialog-description"
            className="p-3.5 rounded-xl border border-amber-500/30 bg-amber-500/10 text-amber-200 text-xs flex flex-col gap-2"
          >
            <div className="flex items-center gap-2 font-semibold text-amber-300">
              <Lock className="w-4 h-4" />
              <span>Compliance Legal Hold Active (HTTP 423)</span>
            </div>
            <p className="text-amber-200/80 leading-relaxed">
              This review record and its AST artifacts are locked under an active enterprise compliance
              legal hold. Purging or expunging this dataset is strictly restricted by your organization&apos;s
              retention policies until the audit hold is lifted by a Compliance Officer.
            </p>
          </div>
        ) : (
          <div
            id="delete-dialog-description"
            className="text-xs text-white/70 leading-relaxed"
          >
            Are you sure you want to delete this review? This will permanently purge the uploaded code,
            AST representations, and all associated findings from your tenant storage. An immutable
            deletion event will be recorded in the audit log.
          </div>
        )}

        <div className="flex items-center justify-end gap-3 pt-2 border-t border-white/10">
          <button
            onClick={onClose}
            className={`px-4 py-2 rounded-full border border-white/20 bg-transparent text-xs font-medium text-white/70 hover:text-white hover:bg-white/5 transition-colors cursor-pointer ${focusRing}`}
          >
            {legalHold ? 'Close' : 'Cancel'}
          </button>
          {!legalHold && (
            <button
              onClick={() => {
                onConfirm();
                onClose();
              }}
              className={`px-4 py-2 rounded-full bg-rose-600 hover:bg-rose-500 text-xs font-medium text-white transition-colors flex items-center gap-1.5 cursor-pointer shadow-sm ${focusRing}`}
            >
              <Trash2 className="w-3.5 h-3.5" />
              <span>Confirm Permanent Deletion</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
