'use client';

import React, { useState } from 'react';
import { X, Play, RefreshCw, Database, Cpu, Terminal, ArrowRight } from 'lucide-react';
import { useModalA11y } from '@/lib/useFocusTrap';
import { focusRing } from '@/lib/styles';

interface DemoModalProps {
  isOpen: boolean;
  onClose: () => void;
  isAegisMode?: boolean;
  onOpenConsole?: () => void;
}

interface AgentJob {
  id: string;
  name: string;
  trigger: string;
  cadence: string;
  status: 'idle' | 'running' | 'completed' | 'verified';
  agent: string;
  lastRun: string;
  memoryState: Record<string, any>;
}

export const DemoModal: React.FC<DemoModalProps> = ({
  isOpen,
  onClose,
  isAegisMode = true,
  onOpenConsole,
}) => {
  const modalRef = useModalA11y(isOpen, onClose);

  if (!isOpen) return null;

  const [activeJobId, setActiveJobId] = useState<string>('job-1');
  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [logs, setLogs] = useState<string[]>([
    '[INIT] Vigil Kernel v2.4 initialized with deterministic AST parser',
    '[SYNC] Connected to distributed taint graph engine (latency: 0.8ms)',
    '[SECURITY] 4 AST taint rules registered with zero false-positive policy',
  ]);

  const jobs: AgentJob[] = isAegisMode
    ? [
        {
          id: 'job-1',
          name: 'orders-gateway.py Taint Analysis',
          trigger: 'PR #104 Open',
          cadence: 'On Trigger',
          status: 'verified',
          agent: 'A3 Security Reasoner',
          lastRun: '12 seconds ago',
          memoryState: {
            taintSource: 'request.query_params["status"]',
            astNode: 'Call[cursor.execute]',
            cweDetected: 'CWE-89',
            confidence: 0.98,
          },
        },
        {
          id: 'job-2',
          name: 'auth-middleware.py Reentrancy Check',
          trigger: 'git push main',
          cadence: 'Continuous',
          status: 'completed',
          agent: 'A2 Static Analysis',
          lastRun: '3 mins ago',
          memoryState: {
            functionsScanned: 18,
            semgrepRules: 42,
            findings: 0,
          },
        },
        {
          id: 'job-3',
          name: 'gVisor Sandbox Patch Verification',
          trigger: 'Automated Triaged Fix',
          cadence: 'Event Driven',
          status: 'idle',
          agent: 'A7 MicroVM Sandbox',
          lastRun: '18 mins ago',
          memoryState: {
            sandboxRuntime: 'runsc-2026',
            networkIsolation: true,
            exitCode: 0,
          },
        },
      ]
    : [];

  const currentJob = jobs.find((j) => j.id === activeJobId) || jobs[0];

  const handleTrigger = (jobId: string) => {
    setActiveJobId(jobId);
    setIsRunning(true);
    setLogs((prev) => [
      ...prev,
      `[TASK] Dispatched agent execution for job: ${jobId}`,
      `[RUNNING] Allocating isolated AST evaluator...`,
    ]);

    setTimeout(() => {
      setLogs((prev) => [
        ...prev,
        `[SUCCESS] Run completed cleanly. Context persisted to durable storage.`,
      ]);
      setIsRunning(false);
    }, 2100);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-in fade-in duration-200">
      <div
        ref={modalRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="demo-modal-title"
        aria-describedby="demo-modal-description"
        className="relative w-full max-w-4xl bg-[#09090b] border border-white/15 rounded-xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/10 bg-white/[0.02]">
          <div className="flex items-center gap-3">
            <div className="w-2.5 h-2.5 rounded-full bg-white/30 animate-pulse" />
            <h2 id="demo-modal-title" className="text-sm font-semibold tracking-wide text-white uppercase font-mono">
              Vigil Autonomous Code Review Engine Demo
            </h2>
          </div>
          <button
            onClick={onClose}
            className={`text-white/40 hover:text-white transition-colors p-1 rounded-md hover:bg-white/5 ${focusRing}`}
            aria-label="Close modal"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="grid grid-cols-1 md:grid-cols-12 divide-y md:divide-y-0 md:divide-x divide-white/10 overflow-y-auto">
          {/* Left Column: Scheduled Agents List */}
          <div className="md:col-span-5 p-5 space-y-3 bg-black/40">
            <div id="demo-modal-description" className="text-[11px] font-mono uppercase tracking-widest text-white/40 pb-1">
              Active Schedules
            </div>
            <div className="space-y-2">
              {jobs.map((job) => (
                <div
                  key={job.id}
                  role="button"
                  tabIndex={0}
                  aria-label={job.name}
                  onClick={() => setActiveJobId(job.id)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      setActiveJobId(job.id);
                    }
                  }}
                  className={`p-3.5 rounded-lg border cursor-pointer transition-all ${focusRing} ${
                    activeJobId === job.id
                      ? 'bg-white/10 border-white/40 text-white shadow-lg'
                      : 'bg-white/[0.02] border-white/5 text-white/70 hover:bg-white/5 hover:border-white/20'
                  }`}
                >
                  <div className="flex items-center justify-between text-xs font-semibold">
                    <span className="truncate pr-2">{job.name}</span>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-white/10 text-white/80">
                      {job.cadence}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 mt-2 text-[11px] text-white/40">
                    <Cpu className="w-3.5 h-3.5" />
                    <span>{job.agent}</span>
                  </div>
                </div>
              ))}
            </div>

            <div className="pt-4 border-t border-white/10">
              <button
                type="button"
                onClick={() => handleTrigger(activeJobId)}
                disabled={isRunning}
                className={`w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-full bg-white text-black font-semibold text-xs uppercase tracking-wider hover:bg-white/90 transition-all disabled:opacity-50 cursor-pointer shadow-md ${focusRing}`}
              >
                {isRunning ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    <span>Executing Run...</span>
                  </>
                ) : (
                  <>
                    <Play className="w-4 h-4 fill-current" />
                    <span>Trigger Immediate Run</span>
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Right Column: Context State & Live Execution Output */}
          <div className="md:col-span-7 p-5 space-y-4 bg-[#0a0a0c]">
            <div>
              <div className="flex items-center justify-between text-xs text-white/50 mb-2">
                <span className="font-mono uppercase tracking-wider text-[11px] flex items-center gap-1.5">
                  <Database className="w-3.5 h-3.5" />
                  Durable Context State
                </span>
                <span className="text-[10px] text-white/60 font-mono">Sync Status: Healthy</span>
              </div>
              <pre className="p-3.5 rounded-lg bg-black border border-white/10 font-mono text-[11px] text-white/70/90 overflow-x-auto max-h-40 leading-relaxed">
                {JSON.stringify(currentJob?.memoryState || {}, null, 2)}
              </pre>
            </div>

            {/* Live Telemetry Log */}
            <div>
              <div className="flex items-center justify-between text-xs text-white/50 mb-2">
                <span className="font-mono uppercase tracking-wider text-[11px] flex items-center gap-1.5">
                  <Terminal className="w-3.5 h-3.5" />
                  Execution Event Stream
                </span>
                <span className="text-[10px] text-white/40 font-mono">Auto-Scroll ON</span>
              </div>
              <div className="p-3.5 rounded-lg bg-black border border-white/10 font-mono text-[11px] text-white/80 space-y-1.5 max-h-48 overflow-y-auto">
                {logs.map((log, idx) => (
                  <div key={idx} className="flex items-start gap-2">
                    <span className="text-white/30 select-none">&gt;</span>
                    <span
                      className={
                        log.includes('[SUCCESS]')
                          ? 'text-white/60'
                          : log.includes('[DISPATCH]')
                          ? 'text-sky-300'
                          : 'text-white/70'
                      }
                    >
                      {log}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-white/10 bg-black/60 flex items-center justify-between text-xs text-white/40">
          <span>Deterministic Scheduler Guarantee: 99.999% SLA</span>
          <div className="flex items-center gap-3">
            {onOpenConsole && (
              <button
                onClick={() => {
                  onClose();
                  onOpenConsole();
                }}
                className={`px-3 py-1 rounded-full bg-white text-black font-semibold text-xs flex items-center gap-1.5 hover:bg-white/90 transition-colors cursor-pointer ${focusRing}`}
              >
                <span>Launch Review Console</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            )}
            <button
              onClick={onClose}
              className={`text-white hover:text-white/80 font-medium tracking-wide transition-colors cursor-pointer px-2 py-1 rounded ${focusRing}`}
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
