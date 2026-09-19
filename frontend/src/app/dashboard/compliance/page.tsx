'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function DashboardCompliancePage() {
  const router = useRouter();

  useEffect(() => {
    router.replace('/dashboard/reviews');
  }, [router]);

  return null;
}
