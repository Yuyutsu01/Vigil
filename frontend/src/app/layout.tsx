import type { Metadata } from 'next';
import '../styles/globals.css';
import { AuthProvider } from '@/context/AuthContext';

export const metadata: Metadata = {
  title: 'Vigil | Autonomous Security Operations Engine',
  description:
    'Continuous AST-grounded reasoning, deterministic patch generation, and zero-execution CI/CD governance across your multi-agent reviews.',
  icons: {
    icon: '/images/vigil-logo-square.png',
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const isMockMode = process.env.NEXT_PUBLIC_API_MODE === 'mock';

  return (
    <html lang="en" className="dark">
      <head>
        {/* Google Fonts Typography */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="bg-black text-white font-sans antialiased selection:bg-white selection:text-black min-h-screen">
        <AuthProvider>
          {/* Mock Mode Diagnostic Banner (Visible only when mock fixture mode is configured) */}
          {isMockMode && (
            <div className="bg-amber-500/15 border-b border-amber-500/30 text-amber-200 px-4 py-1 text-center text-xs font-mono select-none sticky top-0 z-[60] backdrop-blur-md">
              <span className="font-semibold mr-2">[MOCK DATA MODE]</span>
              Using isolated mock fixtures. Set{' '}
              <code className="bg-amber-950/40 px-1 py-0.5 rounded border border-amber-500/30">
                NEXT_PUBLIC_API_MODE=real
              </code>{' '}
              in <code className="bg-amber-950/40 px-1 py-0.5 rounded">.env.local</code> to connect to
              FastAPI backend.
            </div>
          )}

          {children}
        </AuthProvider>
      </body>
    </html>
  );
}
