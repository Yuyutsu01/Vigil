'use client';

import React from 'react';
import { useRouter } from 'next/navigation';
import { PatchesView } from '@/components/vigil/PatchesView';

export default function DashboardPatchesPage() {
  const router = useRouter();

  const handleSelectReview = (reviewId: string) => {
    router.push(`/dashboard/reviews/${reviewId}`);
  };

  return <PatchesView onSelectReview={handleSelectReview} />;
}
