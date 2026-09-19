'use client';

import React from 'react';
import { useRouter } from 'next/navigation';
import { NewReviewView } from '@/components/vigil/NewReviewView';
import { Review, Finding } from '@/lib/types';

export default function NewReviewPage() {
  const router = useRouter();

  const handleCreateReview = (newReview: Review, newFindings?: Finding[]) => {
    // In production, this persists to POST /v1/reviews or backend.
    // In our client, we route directly to the reviews workspace.
    router.push(`/dashboard/reviews/${newReview.id}`);
  };

  const handleCancel = () => {
    router.push('/dashboard/reviews');
  };

  return (
    <div className="p-6 max-w-5xl mx-auto overflow-y-auto min-h-full">
      <NewReviewView
        onCreateReview={handleCreateReview}
        onCancel={handleCancel}
      />
    </div>
  );
}
