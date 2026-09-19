'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';

// Navigation anchor links for landing page sections with plain-language labels
const NAV_LINKS = [
  { href: '#about', label: 'About' },
  { href: '#features', label: 'Capabilities' },
  { href: '#benchmarks', label: 'Results' },
  { href: '#execution', label: 'Pipeline' },
  { href: '#verification', label: 'Security' },
  { href: '#insights', label: 'Product' },
  { href: '#testimonials', label: 'Customers' },
];

function Arrow() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      aria-hidden="true"
    >
      <path
        d="M12.5 18C12.5 18 18.5 13.5811 18.5 12C18.5 10.4188 12.5 6 12.5 6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M5.50005 18C5.50005 18 11.5 13.5811 11.5 12C11.5 10.4188 5.5 6 5.5 6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

interface NavbarProps {
  onGetStarted?: () => void;
  onLinkClick?: (href: string) => void;
}

export default function Navbar({ onGetStarted, onLinkClick }: NavbarProps) {
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  // Lock body scroll while mobile menu drawer is open
  useEffect(() => {
    document.body.style.overflow = open ? 'hidden' : '';
    return () => {
      document.body.style.overflow = '';
    };
  }, [open]);

  // Track scroll position to enhance background opacity on offset
  useEffect(() => {
    const onScroll = () => {
      setScrolled(window.scrollY > 20);
    };

    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  const handleNav = (href: string) => {
    if (onLinkClick) {
      onLinkClick(href);
    } else {
      const id = href.replace('#', '');
      const elem = document.getElementById(id);
      if (elem) {
        elem.scrollIntoView({ behavior: 'smooth' });
      }
    }
  };

  return (
    <header
      className={`fixed top-0 inset-x-0 z-50 transition-all duration-300 border-b ${
        scrolled
          ? 'bg-black/90 backdrop-blur-2xl border-white/20 shadow-2xl shadow-black/80'
          : 'bg-black/70 backdrop-blur-xl border-white/15'
      }`}
    >
      {/* Specular top rim light */}
      <div className="pointer-events-none absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-white/30 to-transparent" />

      <nav className="mx-auto w-full max-w-[1560px] h-[72px] sm:h-20 flex items-center justify-between px-6 sm:px-10 lg:px-14 xl:px-16">
        {/* Brand Logo & Home Anchor */}
        <Link
          href="/"
          onClick={(e) => {
            if (window.location.pathname === '/') {
              e.preventDefault();
              window.scrollTo({ top: 0, behavior: 'smooth' });
            }
          }}
          className="group flex items-center gap-3 cursor-pointer py-1.5"
          aria-label="Vigil home"
        >
          <img
            src="/images/vigil-logo.png"
            alt="Vigil"
            className="h-7 sm:h-8 md:h-9 w-auto transition-transform duration-300 group-hover:scale-105"
          />
        </Link>

        {/* Desktop Navigation Links — Broader & High-Readability Glossy Glassmorphic Pills */}
        <div className="hidden lg:flex items-center gap-2 xl:gap-3">
          {NAV_LINKS.map((link) => (
            <a
              key={link.label}
              href={link.href}
              onClick={(e) => {
                e.preventDefault();
                handleNav(link.href);
              }}
              className="group relative px-4 py-2 rounded-full text-[14px] xl:text-[14.5px] font-medium tracking-normal text-zinc-200 hover:text-white transition-all duration-200 border border-transparent hover:border-white/25 hover:bg-white/[0.1] hover:backdrop-blur-md hover:shadow-[0_0_20px_rgba(255,255,255,0.09)] cursor-pointer active:scale-95"
            >
              <span className="relative z-10">{link.label}</span>
              {/* Glossy specular top reflection inside hover pill */}
              <span className="pointer-events-none absolute inset-0 rounded-full bg-gradient-to-b from-white/[0.18] to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-200" />
            </a>
          ))}
        </div>

        {/* Desktop Action CTAs: SecOps Console Link & Star Button */}
        <div className="hidden md:flex items-center gap-4">
          <Link
            href="/dashboard"
            className="group relative px-4 py-2 rounded-full text-xs font-mono tracking-wider text-zinc-200 hover:text-white uppercase border border-white/20 bg-white/[0.04] hover:bg-white/[0.12] hover:border-white/40 transition-all duration-200 shadow-sm hover:shadow-[0_0_20px_rgba(255,255,255,0.1)]"
          >
            <span className="relative z-10 flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-white/30 animate-pulse" />
              SecOps Console
            </span>
            <span className="pointer-events-none absolute inset-0 rounded-full bg-gradient-to-b from-white/[0.15] to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
          </Link>

          <button
            type="button"
            onClick={onGetStarted}
            style={{
              '--duration': 3,
              '--light-width': '120px',
              '--light-color': '#FAFAFA',
              '--border-width': '2px',
              isolation: 'isolate',
              '--path': "path('M 0 0 H 145 V 40 H 0 V 0')",
            } as React.CSSProperties}
            className="group/star-button relative z-[3] inline-flex h-10 items-center justify-center gap-2 overflow-hidden whitespace-nowrap rounded-3xl border border-slate-200/60 px-5 py-2.5 text-xs sm:text-[13px] font-semibold tracking-wide transition-all duration-200 cursor-pointer hover:border-white hover:scale-[1.02] active:scale-95 disabled:pointer-events-none disabled:opacity-50 shadow-[0_0_20px_rgba(255,255,255,0.12)]"
          >
            <div
              className="absolute inset-0 aspect-square animate-star-btn bg-[radial-gradient(ellipse_closest-side_at_center,var(--light-color),transparent,transparent)]"
              style={{
                offsetPath: 'var(--path)',
                offsetDistance: '0%',
                width: 'var(--light-width)',
              }}
            />
            <div
              className="absolute inset-[2px] z-[4] overflow-hidden rounded-[inherit] border-black/10 text-white dark:border-white/15 dark:text-black"
              style={{ borderWidth: 'var(--border-width)', backgroundColor: '#000000' }}
              aria-hidden="true"
            >
              <svg
                width="100%"
                height="100%"
                preserveAspectRatio="none"
                viewBox="0 0 100 40"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                <g clipPath="url(#clip0_nav_star)">
                  <path
                    d="M32.34 26.68C32.34 26.3152 32.0445 26.02 31.68 26.02C31.3155 26.02 31.02 26.3152 31.02 26.68C31.02 27.0448 31.3155 27.34 31.68 27.34C32.0445 27.34 32.34 27.0448 32.34 26.68Z"
                    fill="black"
                  />
                </g>
                <defs>
                  <clipPath id="clip0_nav_star">
                    <rect width="100" height="40" fill="white" />
                  </clipPath>
                </defs>
              </svg>
            </div>
            <span className="relative z-10 inline-flex items-center gap-1.5 whitespace-nowrap text-white font-medium">
              GET STARTED
              <Arrow />
            </span>
          </button>
        </div>

        {/* Mobile menu toggle */}
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="p-2 text-white transition-colors lg:hidden cursor-pointer"
          aria-label="Toggle menu"
          aria-expanded={open}
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            {open ? (
              <>
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </>
            ) : (
              <>
                <line x1="4" x2="20" y1="12" y2="12" />
                <line x1="4" x2="20" y1="6" y2="6" />
                <line x1="4" x2="20" y1="18" y2="18" />
              </>
            )}
          </svg>
        </button>
      </nav>

      {/* Mobile drawer overlay */}
      <div
        className={`fixed inset-0 z-40 bg-black transition-all duration-300 lg:hidden ${
          open ? 'pointer-events-auto opacity-100' : 'pointer-events-none opacity-0'
        }`}
        style={{ top: '72px' }}
      >
        <div className="flex h-[calc(100vh-72px)] flex-col px-6 pb-8 pt-8 justify-between">
          <div className="flex flex-col gap-5">
            {NAV_LINKS.map((link) => (
              <a
                key={link.label}
                href={link.href}
                onClick={(e) => {
                  e.preventDefault();
                  setOpen(false);
                  handleNav(link.href);
                }}
                className="font-display text-xl text-white hover:text-zinc-400 transition-colors cursor-pointer"
              >
                {link.label}
              </a>
            ))}
            <Link
              href="/dashboard"
              onClick={() => setOpen(false)}
              className="font-mono text-sm uppercase tracking-wider text-white/60 pt-2"
            >
              Launch SecOps Console →
            </Link>
          </div>

          <div className="border-t border-white/10 pt-6">
            <button
              type="button"
              onClick={() => {
                setOpen(false);
                if (onGetStarted) onGetStarted();
              }}
              className="w-full py-3 rounded-full bg-white text-black font-semibold text-sm tracking-wider uppercase transition-all hover:bg-zinc-200 cursor-pointer flex items-center justify-center gap-2"
            >
              <span>GET STARTED</span>
              <Arrow />
            </button>
          </div>
        </div>
      </div>
    </header>
  );
}
