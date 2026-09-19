'use client';

import React, { useState } from 'react';
import Navbar from '@/components/landing/Navbar';
import Hero from '@/components/landing/Hero';
import { BrandLogos } from '@/components/landing/BrandLogos';
import { ContentSections } from '@/components/landing/ContentSections';
import { StatefulExecutionSection } from '@/components/landing/StatefulExecutionSection';
import { DurableAutonomySection } from '@/components/landing/DurableAutonomySection';
import { AgentInsightsSection } from '@/components/landing/AgentInsightsSection';
import { CelestialCTASection } from '@/components/landing/CelestialCTASection';
import { Footer } from '@/components/landing/Footer';
import { DemoModal } from '@/components/landing/DemoModal';
import { GetStartedModal } from '@/components/landing/GetStartedModal';

export default function LandingPage() {
  // Modal states for live demo terminal and SDK get started dialog
  const [isDemoModalOpen, setIsDemoModalOpen] = useState(false);
  const [isGetStartedModalOpen, setIsGetStartedModalOpen] = useState(false);

  // Handlers for modal interactions
  const handleOpenDemo = () => setIsDemoModalOpen(true);
  const handleOpenGetStarted = () => setIsGetStartedModalOpen(true);

  // Smooth scroll dispatching for anchor links
  const handleLinkClick = (item: string) => {
    const rawId = item.startsWith('#') ? item.slice(1) : item.toLowerCase();
    const map: Record<string, string> = {
      about: 'about',
      capabilities: 'features',
      features: 'features',
      benchmarks: 'benchmarks',
      testimonials: 'testimonials',
      customers: 'testimonials',
      pipeline: 'execution',
      execution: 'execution',
      verification: 'verification',
      insights: 'insights',
      fleet: 'insights',
      proof: 'testimonials',
      cta: 'cta',
    };
    const targetId = map[rawId] || rawId;
    const element = document.getElementById(targetId);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <div className="relative min-h-screen bg-black text-white selection:bg-white selection:text-black">
      {/* 1. Fixed Top Navigation Bar */}
      <Navbar onGetStarted={handleOpenGetStarted} onLinkClick={handleLinkClick} />

      {/* Main content landmark for WCAG 2.1 AA landmark-one-main compliance */}
      <main id="main-content">
        {/* 2. Screen-Fit 3D Hero with Particle Vortex */}
        <Hero onGetStarted={handleOpenGetStarted} onRequestDemo={handleOpenDemo} />

        {/* 3. Verified Platform Integrations Strip */}
        <BrandLogos />

        {/* 4. Primary Mission Statement, Capabilities & Empirical Benchmarks (#about, #features, #benchmarks) */}
        <ContentSections
          onOpenGetStarted={handleOpenGetStarted}
          onOpenDemo={handleOpenDemo}
        />

        {/* 5. Pipeline Execution Engine (#execution) */}
        <StatefulExecutionSection
          onGetStarted={handleOpenGetStarted}
          onRequestDemo={handleOpenDemo}
        />

        {/* 6. Verification & CI/CD Governance (#verification) */}
        <DurableAutonomySection
          onGetStarted={handleOpenGetStarted}
          onRequestDemo={handleOpenDemo}
        />

        {/* 7. Multi-Agent Fleet Telemetry with 14-Agent Math Breakdown (#insights) */}
        <AgentInsightsSection
          onGetStarted={handleOpenGetStarted}
          onRequestDemo={handleOpenDemo}
        />

        {/* 8. Celestial CTA Section (#cta) */}
        <CelestialCTASection
          onGetStarted={handleOpenGetStarted}
          onRequestDemo={handleOpenDemo}
        />
      </main>

      {/* 9. Global Footer Directory & Legal Disclosures */}
      <Footer
        onLinkClick={handleLinkClick}
        onRequestDemo={handleOpenDemo}
        onGetStarted={handleOpenGetStarted}
      />

      {/* Interactive Modals */}
      <DemoModal
        isOpen={isDemoModalOpen}
        onClose={() => setIsDemoModalOpen(false)}
      />
      <GetStartedModal
        isOpen={isGetStartedModalOpen}
        onClose={() => setIsGetStartedModalOpen(false)}
      />
    </div>
  );
}
