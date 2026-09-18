import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Vigil — Agentic Code Security Review',
  description:
    'Vigil Phase 1: AI-powered static code analysis for Python, JavaScript, and TypeScript. ' +
    'Detects security vulnerabilities and code quality issues — submitted code is never executed.',
  keywords: ['code review', 'security', 'static analysis', 'SAST', 'LLM'],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
