'use client';

import React from 'react';
import { useRouter } from 'next/navigation';
import { GitHubView } from '@/components/vigil/GitHubView';

export default function DashboardGitHubPage() {
  const router = useRouter();

  const handleSelectReview = (reviewId: string) => {
    router.push(`/dashboard/reviews/${reviewId}`);
  };

  return <GitHubView onSelectReview={handleSelectReview} />;
}
