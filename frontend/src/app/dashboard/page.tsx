'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { DashboardView } from '@/components/vigil/DashboardView';
import { api } from '@/lib/api';
import { Review } from '@/lib/types';

export default function DashboardOverviewPage() {
  const router = useRouter();
  const [reviews, setReviews] = useState<Review[]>([]);

  useEffect(() => {
    let mounted = true;
    api.listReviews({ limit: 10 })
      .then((res) => {
        if (mounted) setReviews(res.items);
      })
      .catch((err) => {
        console.error('Failed to fetch recent reviews for dashboard:', err);
        if (mounted) setReviews([]);
      });
    return () => {
      mounted = false;
    };
  }, []);

  const handleSelectReview = (reviewId: string) => {
    router.push(`/dashboard/reviews/${reviewId}`);
  };

  const handleNewReview = () => {
    router.push('/dashboard/reviews/new');
  };

  return (
    <DashboardView
      reviews={reviews}
      onSelectReview={handleSelectReview}
      onNewReview={handleNewReview}
    />
  );
}
