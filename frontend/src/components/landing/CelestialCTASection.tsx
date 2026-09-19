'use client';

import React, { useEffect, useRef } from 'react';

interface CelestialCTASectionProps {
  onGetStarted?: () => void;
  onRequestDemo?: () => void;
}

export const CelestialCTASection: React.FC<CelestialCTASectionProps> = ({
  onGetStarted,
  onRequestDemo,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d', { alpha: false });
    if (!ctx) return;

    let animFrameId: number;
    let W = 0;
    let H = 0;
    let dpr = 1;

    interface Streak {
      x: number;
      y: number;
      length: number;
      speed: number;
      width: number;
      baseAlpha: number;
      flickerPhase: number;
      flickerFreq: number;
      isLeader: boolean;
      driftX: number;
    }

    interface CelestialNode {
      x: number;
      y: number;
      speed: number;
      size: number;
      phase: number;
    }

    let streaks: Streak[] = [];
    let nodes: CelestialNode[] = [];

    const initArrays = (count: number, nodeCount: number) => {
      streaks = Array.from({ length: count }, () => {
        const rand = Math.random();
        let length: number;
        let width: number;
        let baseAlpha: number;
        let speed: number;
        let isLeader = false;

        if (rand < 0.1) {
          isLeader = true;
          length = 60 + Math.random() * 80;
          width = 1.1 + Math.random() * 0.7;
          baseAlpha = 0.45 + Math.random() * 0.35;
          speed = 0.0018 + Math.random() * 0.0018;
        } else if (rand < 0.4) {
          length = 35 + Math.random() * 45;
          width = 0.7 + Math.random() * 0.4;
          baseAlpha = 0.2 + Math.random() * 0.22;
          speed = 0.0012 + Math.random() * 0.0014;
        } else {
          length = 15 + Math.random() * 30;
          width = 0.35 + Math.random() * 0.35;
          baseAlpha = 0.08 + Math.random() * 0.15;
          speed = 0.0007 + Math.random() * 0.001;
        }

        return {
          x: Math.random(),
          y: Math.random(),
          length,
          speed,
          width,
          baseAlpha,
          flickerPhase: Math.random() * Math.PI * 2,
          flickerFreq: 1.5 + Math.random() * 3,
          isLeader,
          driftX: (Math.random() - 0.5) * 0.00008,
        };
      });

      nodes = Array.from({ length: nodeCount }, () => ({
        x: Math.random(),
        y: Math.random(),
        speed: 0.0006 + Math.random() * 0.0012,
        size: 0.8 + Math.random() * 1.4,
        phase: Math.random() * Math.PI * 2,
      }));
    };

    const handleResize = () => {
      W = canvas.clientWidth;
      H = canvas.clientHeight;
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.floor(W * dpr);
      canvas.height = Math.floor(H * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const count = W < 640 ? 180 : W < 1100 ? 300 : 420;
      const nodeCount = W < 640 ? 40 : 80;
      initArrays(count, nodeCount);
    };

    handleResize();
    const resizeObserver = new ResizeObserver(handleResize);
    resizeObserver.observe(canvas);

    let t = 0;
    let lastTime = performance.now();
    const TARGET_INTERVAL = 1000 / 60;

    const render = (now: DOMHighResTimeStamp) => {
      animFrameId = requestAnimationFrame(render);
      const delta = now - lastTime;
      if (delta < TARGET_INTERVAL - 1.5) return;
      const normDelta = Math.min(delta / TARGET_INTERVAL, 2.5);
      lastTime = now - (delta % TARGET_INTERVAL);
      t += 0.004 * normDelta;

      ctx.fillStyle = '#000000';
      ctx.fillRect(0, 0, W, H);

      // Layer 1: Twinkling Star Nodes
      for (let i = 0; i < nodes.length; i++) {
        const n = nodes[i];
        n.y -= n.speed * normDelta;
        if (n.y < 0) n.y = 1;
        const twinkle = 0.2 + 0.8 * Math.abs(Math.sin(t * 5 + n.phase));
        const alpha = 0.15 + 0.55 * twinkle;
        ctx.fillStyle = `rgba(255, 255, 255, ${alpha.toFixed(3)})`;
        ctx.beginPath();
        ctx.arc(n.x * W, n.y * H, n.size, 0, Math.PI * 2);
        ctx.fill();
      }

      // Layer 2: Vertical Celestial Space Streaks Moving Upward
      ctx.lineCap = 'round';
      for (let i = 0; i < streaks.length; i++) {
        const s = streaks[i];
        s.y -= s.speed * normDelta;
        s.x += s.driftX * normDelta;
        if (s.x < 0) s.x = 1;
        if (s.x > 1) s.x = 0;
        const px = s.x * W;
        const py = s.y * H;
        if (s.y < -s.length / H) {
          s.y = 1 + (Math.random() * s.length) / H;
          s.x = Math.random();
        }

        const tailY = py + s.length;
        const grad = ctx.createLinearGradient(px, py, px, tailY);
        const flick = 0.82 + 0.18 * Math.sin(t * s.flickerFreq + s.flickerPhase);
        const peakAlpha = Math.min(1, s.baseAlpha * flick);
        grad.addColorStop(0, `rgba(255, 255, 255, ${peakAlpha.toFixed(3)})`);
        grad.addColorStop(0.35, `rgba(255, 255, 255, ${(peakAlpha * 0.7).toFixed(3)})`);
        grad.addColorStop(1, 'rgba(255, 255, 255, 0)');
        ctx.strokeStyle = grad;
        ctx.lineWidth = s.width;
        ctx.beginPath();
        ctx.moveTo(px, py);
        ctx.lineTo(px, tailY);
        ctx.stroke();

        if (s.isLeader && flick > 0.88) {
          ctx.fillStyle = `rgba(255, 255, 255, ${(peakAlpha * 0.8).toFixed(3)})`;
          ctx.beginPath();
          ctx.arc(px, py, s.width * 1.2, 0, Math.PI * 2);
          ctx.fill();
        }
      }

      // Layer 3: Vignette
      const radGrad = ctx.createRadialGradient(
        W / 2,
        H / 2,
        Math.min(W, H) * 0.15,
        W / 2,
        H / 2,
        Math.max(W, H) * 0.75
      );
      radGrad.addColorStop(0, 'rgba(0, 0, 0, 0.45)');
      radGrad.addColorStop(0.6, 'rgba(0, 0, 0, 0.15)');
      radGrad.addColorStop(1, 'rgba(0, 0, 0, 0.6)');
      ctx.fillStyle = radGrad;
      ctx.fillRect(0, 0, W, H);
    };

    animFrameId = requestAnimationFrame(render);
    const handleVisibilityChange = () => {
      if (document.hidden) cancelAnimationFrame(animFrameId);
      else {
        lastTime = performance.now();
        animFrameId = requestAnimationFrame(render);
      }
    };
    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => {
      cancelAnimationFrame(animFrameId);
      resizeObserver.disconnect();
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, []);

  return (
    <section id="cta" className="relative z-20 w-full bg-black text-white py-32 px-4 sm:px-6 md:px-10 border-t border-white/10 overflow-hidden text-center">
      {/* Interactive Celestial Canvas Animation Background */}
      <canvas
        ref={canvasRef}
        className="pointer-events-none absolute inset-0 z-0 w-full h-full opacity-60"
      />

      <div className="max-w-4xl mx-auto relative z-10 flex flex-col items-center">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-white/20 bg-white/5 text-xs md:text-sm font-mono uppercase tracking-widest text-cyan-400/80 mb-6">
          ▲ CODE REVIEW &amp; SECURITY
        </div>
        <h2 className="text-4xl sm:text-6xl font-normal tracking-tight text-white mb-6">
          Stop bugs and vulnerabilities before they reach production.
        </h2>
        <p className="text-base sm:text-lg text-white/70 max-w-xl mb-10 leading-relaxed">
          Connect Vigil to your GitHub repositories in minutes to get clear, automated code reviews and safe fix suggestions on every pull request.
        </p>
        <div className="flex flex-col sm:flex-row items-center gap-4">
          <button
            onClick={onGetStarted}
            className="w-full sm:w-auto px-8 py-3.5 rounded-full bg-white text-black font-semibold text-xs uppercase tracking-wider hover:bg-white/90 transition-all cursor-pointer shadow-lg"
          >
            Start Free Audit
          </button>
          <button
            onClick={onRequestDemo}
            className="w-full sm:w-auto px-8 py-3.5 rounded-full border border-white/30 text-white font-semibold text-xs uppercase tracking-wider hover:bg-white/10 transition-all cursor-pointer"
          >
            Request Enterprise Demo
          </button>
        </div>
      </div>
    </section>
  );
};
