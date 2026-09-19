'use client';

import React, { useState } from 'react';
import { ThumbsUp, ThumbsDown, Check, MessageSquare } from 'lucide-react';
import { Feedback } from '@/lib/types';

import { focusRing } from '@/lib/styles';

interface FeedbackButtonsProps {
  findingId: string;
  initialFeedback?: Feedback;
  onSaveFeedback: (feedback: Feedback) => void;
}

export const FeedbackButtons: React.FC<FeedbackButtonsProps> = ({
  findingId,
  initialFeedback,
  onSaveFeedback,
}) => {
  const [feedback, setFeedback] = useState<Feedback | undefined>(initialFeedback);
  const [isExpanding, setIsExpanding] = useState(false);
  const [reason, setReason] = useState<Feedback['reason']>('false_positive');
  const [comment, setComment] = useState('');
  const [showToast, setShowToast] = useState(false);

  const handleThumbClick = (helpful: boolean) => {
    if (!helpful) {
      setIsExpanding(true);
    } else {
      const fb: Feedback = {
        findingId,
        helpful: true,
        submittedAt: new Date().toISOString(),
      };
      setFeedback(fb);
      onSaveFeedback(fb);
      triggerToast();
    }
  };

  const handleSubmitNegative = (e: React.FormEvent) => {
    e.preventDefault();
    const fb: Feedback = {
      findingId,
      helpful: false,
      reason,
      comment: comment.trim() || undefined,
      submittedAt: new Date().toISOString(),
    };
    setFeedback(fb);
    onSaveFeedback(fb);
    setIsExpanding(false);
    triggerToast();
  };

  const triggerToast = () => {
    setShowToast(true);
    setTimeout(() => setShowToast(false), 2500);
  };

  return (
    <div className="relative flex flex-col gap-2.5 p-3.5 rounded-xl border border-white/10 bg-white/[0.03]">
      {showToast && (
        <div
          role="status"
          aria-live="polite"
          className="absolute -top-9 right-2 bg-black border border-emerald-500/40 text-emerald-300 text-xs px-2.5 py-1 rounded-full shadow-lg flex items-center gap-1.5 animate-in fade-in"
        >
          <Check className="w-3 h-3" />
          <span>Feedback saved to learning loop</span>
        </div>
      )}
      <div className="flex items-center justify-between">
        <span className="text-xs text-white/80 font-medium">Is this finding actionable?</span>
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={() => handleThumbClick(true)}
            aria-label="Mark as useful finding"
            className={`p-1.5 rounded-full border text-xs flex items-center gap-1.5 transition-colors cursor-pointer ${focusRing} ${
              feedback?.helpful === true
                ? 'bg-emerald-500/20 border-emerald-500/40 text-emerald-300'
                : 'bg-white/[0.04] border-white/15 text-white/60 hover:text-white hover:bg-white/10'
            }`}
            title="Mark as helpful finding"
          >
            <ThumbsUp className="w-3.5 h-3.5" />
            <span>Helpful</span>
          </button>
          <button
            type="button"
            onClick={() => handleThumbClick(false)}
            aria-label="Mark as not useful or false positive"
            className={`p-1.5 rounded-full border text-xs flex items-center gap-1.5 transition-colors cursor-pointer ${focusRing} ${
              feedback?.helpful === false
                ? 'bg-rose-500/20 border-rose-500/40 text-rose-300'
                : 'bg-white/[0.04] border-white/15 text-white/60 hover:text-white hover:bg-white/10'
            }`}
            title="Mark as false positive or unhelpful"
          >
            <ThumbsDown className="w-3.5 h-3.5" />
            <span>Report issue</span>
          </button>
        </div>
      </div>

      {feedback && !isExpanding && (
        <div className="text-[11px] text-white/50 font-mono flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
          <span>
            Logged: {feedback.helpful ? 'Verified True Positive' : feedback.reason || 'Reported'}
          </span>
          {feedback.comment && <span className="text-white/40 truncate">({feedback.comment})</span>}
        </div>
      )}

      {isExpanding && (
        <form
          onSubmit={handleSubmitNegative}
          className="flex flex-col gap-2.5 pt-2 border-t border-white/10"
        >
          <div className="flex flex-col gap-1">
            {/* Associated label for screen readers */}
            <label htmlFor="feedback-reason-select" className="text-[11px] text-white/60">Classification reason:</label>
            <select
              id="feedback-reason-select"
              value={reason}
              onChange={(e) => setReason(e.target.value as Feedback['reason'])}
              className={`bg-black border border-white/15 rounded-lg px-2.5 py-1 text-xs text-white focus:outline-none focus:border-white/40 ${focusRing}`}
            >
              <option value="false_positive">False positive (not a real vulnerability)</option>
              <option value="not_actionable">Not actionable in this context</option>
              <option value="duplicate">Duplicate of another finding</option>
              <option value="wrong_severity">Wrong severity rating</option>
              <option value="other">Other / Custom note</option>
            </select>
          </div>
          <div className="flex flex-col gap-1">
            {/* Associated label for screen readers */}
            <label htmlFor="feedback-rationale-input" className="text-[11px] text-white/60 flex items-center gap-1">
              <MessageSquare className="w-3 h-3 text-white/40" />
              Optional rationale:
            </label>
            <input
              id="feedback-rationale-input"
              type="text"
              placeholder="e.g. Input is already validated by upstream middleware..."
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              className={`bg-black border border-white/15 rounded-lg px-2.5 py-1 text-xs text-white placeholder:text-white/30 focus:outline-none focus:border-white/40 ${focusRing}`}
            />
          </div>
          <div className="flex items-center justify-end gap-2 pt-1">
            <button
              type="button"
              onClick={() => setIsExpanding(false)}
              className="px-3 py-1 rounded-full text-xs text-white/50 hover:text-white"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-3.5 py-1 bg-white hover:bg-white/90 text-black rounded-full text-xs font-semibold cursor-pointer transition-colors"
            >
              Save Feedback
            </button>
          </div>
        </form>
      )}
    </div>
  );
};
