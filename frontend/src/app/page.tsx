'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import Navbar from '@/components/landing/Navbar';
import Hero from '@/components/landing/Hero';
import { ContentSections } from '@/components/landing/ContentSections';
import { ProductShowcase } from '@/components/landing/ProductShowcase';
import { StatefulExecutionSection } from '@/components/landing/StatefulExecutionSection';
import { DurableAutonomySection } from '@/components/landing/DurableAutonomySection';
import { AgentInsightsSection } from '@/components/landing/AgentInsightsSection';
import { CelestialCTASection } from '@/components/landing/CelestialCTASection';
import { Footer } from '@/components/landing/Footer';
import { DemoModal } from '@/components/landing/DemoModal';

export default function LandingPage() {
  const router = useRouter();

  // Modal state for interactive live demo terminal simulation
  const [isDemoModalOpen, setIsDemoModalOpen] = useState(false);

  // Handlers for interactions
  const handleOpenDemo = () => setIsDemoModalOpen(true);
  const handleGetStarted = () => router.push('/register');

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
      <Navbar onGetStarted={handleGetStarted} onLinkClick={handleLinkClick} />

      {/* Main content landmark for WCAG 2.1 AA landmark-one-main compliance */}
      <main id="main-content">
        {/* 2. Screen-Fit 3D Hero with Particle Vortex */}
        <Hero onGetStarted={handleGetStarted} onRequestDemo={handleOpenDemo} />

        {/* 3. Product Showcase — Split layout with code editor mock */}
        <ProductShowcase
          onGetStarted={handleGetStarted}
          onRequestDemo={handleOpenDemo}
        />

        {/* 4. Primary Mission Statement, Capabilities & Empirical Benchmarks (#about, #features, #benchmarks) */}
        <ContentSections
          onOpenGetStarted={handleGetStarted}
          onOpenDemo={handleOpenDemo}
        />

        {/* 5. Pipeline Execution Engine (#execution) */}
        <StatefulExecutionSection
          onGetStarted={handleGetStarted}
          onRequestDemo={handleOpenDemo}
        />

        {/* 6. Verification & CI/CD Governance (#verification) */}
        <DurableAutonomySection
          onGetStarted={handleGetStarted}
          onRequestDemo={handleOpenDemo}
        />

        {/* 7. Multi-Agent Fleet Telemetry with 14-Agent Math Breakdown (#insights) */}
        <AgentInsightsSection
          onGetStarted={handleGetStarted}
          onRequestDemo={handleOpenDemo}
        />

        {/* 8. Celestial CTA Section (#cta) */}
        <CelestialCTASection
          onGetStarted={handleGetStarted}
          onRequestDemo={handleOpenDemo}
        />
      </main>

      {/* 9. Global Footer Directory & Legal Disclosures */}
      <Footer
        onLinkClick={handleLinkClick}
        onRequestDemo={handleOpenDemo}
        onGetStarted={handleGetStarted}
      />

      {/* Interactive Simulation Terminal Modal */}
      <DemoModal
        isOpen={isDemoModalOpen}
        onClose={() => setIsDemoModalOpen(false)}
      />
    </div>
  );
}
