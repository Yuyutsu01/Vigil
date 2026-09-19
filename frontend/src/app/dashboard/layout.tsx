'use client';

import React, { useState, useEffect } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { Sidebar } from '@/components/vigil/Sidebar';
import { Topbar } from '@/components/vigil/Topbar';
import { useAuth } from '@/context/AuthContext';
import { VigilNavSection } from '@/lib/types';
import { MOCK_REVIEWS } from '@/data/vigilData';
import { useModalA11y } from '@/lib/useFocusTrap';

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const { isAuthenticated, isLoading } = useAuth();
  const [reviewCount] = useState(MOCK_REVIEWS.length);

  // Sidebar collapse state with localStorage persistence
  const [collapsed, setCollapsed] = useState<boolean>(false);
  const [isMobileDrawerOpen, setIsMobileDrawerOpen] = useState<boolean>(false);

  useEffect(() => {
    try {
      const stored = localStorage.getItem('vigil_sidebar_collapsed');
      if (stored !== null) {
        setCollapsed(stored === 'true');
      } else if (typeof window !== 'undefined' && window.innerWidth < 768) {
        setCollapsed(true);
      }
    } catch {
      // Ignore localStorage errors in restricted environments
    }
  }, []);

  const handleToggleCollapse = () => {
    setCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem('vigil_sidebar_collapsed', String(next));
      } catch {
        // Ignore storage write error
      }
      return next;
    });
  };

  const handleCloseMobileDrawer = () => {
    setIsMobileDrawerOpen(false);
  };

  // WCAG focus trap & Escape listener for mobile drawer
  const drawerRef = useModalA11y(isMobileDrawerOpen, handleCloseMobileDrawer);

  // Map URL paths to Sidebar navigation sections
  const getSectionFromPath = (path: string): VigilNavSection => {
    if (path.includes('/dashboard/reviews/new')) return 'new_review';
    if (path.includes('/dashboard/reviews')) return 'reviews';
    if (path.includes('/dashboard/github')) return 'github';
    if (path.includes('/dashboard/patches')) return 'patches';
    if (path.includes('/dashboard/compliance')) return 'compliance';
    if (path.includes('/dashboard/evaluation')) return 'evaluation';
    if (path.includes('/dashboard/agents')) return 'agents';
    if (path.includes('/dashboard/settings')) return 'settings';
    return 'dashboard';
  };

  const currentSection = getSectionFromPath(pathname);

  // Navigate to corresponding route when sidebar item is clicked
  const handleNavigate = (section: VigilNavSection) => {
    const routeMap: Record<VigilNavSection, string> = {
      dashboard: '/dashboard',
      reviews: '/dashboard/reviews',
      new_review: '/dashboard/reviews/new',
      github: '/dashboard/github',
      patches: '/dashboard/patches',
      compliance: '/dashboard/compliance',
      evaluation: '/dashboard/evaluation',
      agents: '/dashboard/agents',
      settings: '/dashboard/settings',
    };
    if (isMobileDrawerOpen) {
      setIsMobileDrawerOpen(false);
    }
    router.push(routeMap[section] || '/dashboard');
  };

  const handleNewReview = () => {
    if (isMobileDrawerOpen) {
      setIsMobileDrawerOpen(false);
    }
    router.push('/dashboard/reviews/new');
  };

  const handleBackToMarketing = () => {
    router.push('/');
  };

  // Human readable title for topbar based on current route
  const getTitleFromSection = (section: VigilNavSection): string => {
    const titleMap: Record<VigilNavSection, string> = {
      dashboard: 'OPERATIONS OVERVIEW',
      reviews: 'CODE REVIEWS WORKSPACE',
      new_review: 'SUBMISSION STUDIO',
      github: 'GITHUB CI/CD PR GATE',
      patches: 'AUTONOMOUS PATCH VALIDATION',
      compliance: 'COMPLIANCE & AUDIT DOSSIERS',
      evaluation: 'BENCHMARK BENCH & CWE METRICS',
      agents: '14-AGENT DAG FLEET TELEMETRY',
      settings: 'GOVERNANCE & GDPR PURGE',
    };
    return titleMap[section] || 'SECOPS CONSOLE';
  };

  return (
    <div className="flex h-screen bg-black text-white overflow-hidden font-sans">
      {/* Desktop Persistent Left Sidebar (hidden on mobile < 640px) */}
      <div className="hidden sm:flex h-full">
        <Sidebar
          currentSection={currentSection}
          onNavigate={handleNavigate}
          onNewReview={handleNewReview}
          reviewCount={reviewCount}
          collapsed={collapsed}
          onToggleCollapse={handleToggleCollapse}
        />
      </div>

      {/* Mobile Drawer Overlay (< 640px) */}
      {isMobileDrawerOpen && (
        <div
          className="sm:hidden fixed inset-0 z-50 flex bg-black/80 backdrop-blur-sm transition-opacity"
          role="dialog"
          aria-modal="true"
          aria-label="Navigation drawer"
        >
          <div ref={drawerRef} className="h-full">
            <Sidebar
              currentSection={currentSection}
              onNavigate={handleNavigate}
              onNewReview={handleNewReview}
              reviewCount={reviewCount}
              collapsed={false}
              isMobileDrawer={true}
              onCloseMobileDrawer={handleCloseMobileDrawer}
            />
          </div>
          {/* Backdrop click dismiss */}
          <div
            className="flex-1 h-full cursor-pointer"
            onClick={handleCloseMobileDrawer}
            aria-hidden="true"
          />
        </div>
      )}

      {/* Main Operations Container */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Persistent Topbar */}
        <Topbar
          onBackToMarketing={handleBackToMarketing}
          title={getTitleFromSection(currentSection)}
          onOpenMobileDrawer={() => setIsMobileDrawerOpen(true)}
          isMobileDrawerOpen={isMobileDrawerOpen}
        />

        {/* Dynamic Nested Page Content */}
        <main className="flex-1 overflow-y-auto min-h-0 bg-[#070709]">
          {children}
        </main>
      </div>
    </div>
  );
}
