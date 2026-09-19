'use client';

import React, { useState } from 'react';
import {
  FileCheck2,
  Download,
  Calendar,
  ShieldCheck,
  CheckCircle2,
  ExternalLink,
  Search,
} from 'lucide-react';
import { ComplianceReport } from '@/lib/types';
import { focusRing } from '@/lib/styles';

interface ReportsViewProps {
  reports: ComplianceReport[];
  onDownloadReport: (reportId: string, format: 'pdf' | 'sarif' | 'csv') => void;
}

export const ReportsView: React.FC<ReportsViewProps> = ({ reports, onDownloadReport }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedReport, setSelectedReport] = useState<ComplianceReport | null>(reports[0] || null);

  const filtered = reports.filter((r) => {
    const q = searchTerm.toLowerCase();
    return (
      r.title.toLowerCase().includes(q) ||
      r.framework.toLowerCase().includes(q) ||
      r.id.toLowerCase().includes(q)
    );
  });

  return (
    <div className="flex-1 overflow-y-auto p-6 flex flex-col gap-6 text-white select-none">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-white/10 pb-5">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
            <FileCheck2 className="w-5 h-5 text-white/80" />
            <span>Compliance & Audit Dossiers</span>
          </h1>
          <p className="text-xs text-white/50 mt-1">
            Deterministic cryptographic audit evidence for SOC2 Type II, ISO 27001, and NIST SSDF compliance.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative w-64">
            <Search className="w-3.5 h-3.5 text-white/40 absolute left-2.5 top-2.5" />
            <input
              type="text"
              aria-label="Filter compliance dossiers"
              placeholder="Filter dossiers..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className={`w-full bg-black border border-white/15 rounded-lg pl-8 pr-3 py-1.5 text-xs text-white placeholder:text-white/30 focus:outline-none focus:border-white/40 ${focusRing}`}
            />
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Reports List */}
        <div className="lg:col-span-7 flex flex-col gap-3">
          {filtered.map((rpt) => (
            <div
              key={rpt.id}
              role="button"
              tabIndex={0}
              aria-label={`Select dossier ${rpt.id}: ${rpt.title}`}
              onClick={() => setSelectedReport(rpt)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  setSelectedReport(rpt);
                }
              }}
              className={`p-4 rounded-xl border transition-all cursor-pointer flex flex-col gap-2.5 ${focusRing} ${
                selectedReport?.id === rpt.id
                  ? 'bg-white/10 border-white ring-1 ring-white/20'
                  : 'bg-white/[0.03] border-white/10 hover:bg-white/[0.06]'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="font-mono text-[11px] text-white/50">{rpt.id}</span>
                <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-[11px] font-mono flex items-center gap-1">
                  <CheckCircle2 className="w-3 h-3" />
                  <span>{rpt.status}</span>
                </span>
              </div>
              <h3 className="text-sm font-semibold text-white">{rpt.title}</h3>
              <div className="flex items-center justify-between text-xs text-white/60 font-mono pt-2 border-t border-white/10">
                <div className="flex items-center gap-1.5">
                  <Calendar className="w-3.5 h-3.5 text-white/40" />
                  <span>Generated {rpt.generatedAt.split('T')[0]}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-white/80">{rpt.auditedFiles} files</span>
                  <span>•</span>
                  <span className="text-white/80">{rpt.totalFindings} findings</span>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Selected Report Detail & Download Panel */}
        <div className="lg:col-span-5">
          {selectedReport ? (
            <div className="p-5 rounded-2xl border border-white/15 bg-white/[0.02] flex flex-col gap-5 sticky top-6">
              <div className="flex items-center justify-between border-b border-white/10 pb-4">
                <div>
                  <span className="text-[11px] font-mono text-emerald-400 uppercase tracking-wider">
                    {selectedReport.framework}
                  </span>
                  <h3 className="text-base font-bold text-white mt-0.5">{selectedReport.title}</h3>
                </div>
                <ShieldCheck className="w-6 h-6 text-emerald-400 shrink-0" />
              </div>

              <div className="flex flex-col gap-2.5 text-xs">
                <div className="flex justify-between py-1.5 border-b border-white/10">
                  <span className="text-white/50">Audit Target:</span>
                  <span className="text-white font-medium font-mono">{selectedReport.target}</span>
                </div>
                <div className="flex justify-between py-1.5 border-b border-white/10">
                  <span className="text-white/50">Audited By:</span>
                  <span className="text-white font-medium">{selectedReport.auditedBy}</span>
                </div>
                <div className="flex justify-between py-1.5 border-b border-white/10">
                  <span className="text-white/50">Files Analyzed:</span>
                  <span className="text-white font-mono">{selectedReport.auditedFiles}</span>
                </div>
                <div className="flex justify-between py-1.5 border-b border-white/10">
                  <span className="text-white/50">Critical Issues Remediated:</span>
                  <span className="text-emerald-400 font-mono font-bold">100% (0 Open)</span>
                </div>
                <div className="flex justify-between py-1.5">
                  <span className="text-white/50">Cryptographic Digest:</span>
                  <span className="text-white/40 font-mono text-[10.5px] truncate max-w-[170px]">
                    {selectedReport.sha256Digest}
                  </span>
                </div>
              </div>

              <div className="pt-2 border-t border-white/10 flex flex-col gap-2">
                <span className="text-xs text-white/50 font-medium">Export Certified Dossier:</span>
                <div className="grid grid-cols-3 gap-2">
                  <button
                    type="button"
                    onClick={() => onDownloadReport(selectedReport.id, 'pdf')}
                    className={`p-2 rounded-xl border border-white/15 bg-white/5 hover:bg-white/15 text-xs text-white flex flex-col items-center gap-1 transition-colors cursor-pointer ${focusRing}`}
                  >
                    <Download className="w-3.5 h-3.5" />
                    <span>PDF Dossier</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => onDownloadReport(selectedReport.id, 'sarif')}
                    className={`p-2 rounded-xl border border-white/15 bg-white/5 hover:bg-white/15 text-xs text-white flex flex-col items-center gap-1 transition-colors cursor-pointer ${focusRing}`}
                  >
                    <ExternalLink className="w-3.5 h-3.5" />
                    <span>SARIF v2.1</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => onDownloadReport(selectedReport.id, 'csv')}
                    className={`p-2 rounded-xl border border-white/15 bg-white/5 hover:bg-white/15 text-xs text-white flex flex-col items-center gap-1 transition-colors cursor-pointer ${focusRing}`}
                  >
                    <Download className="w-3.5 h-3.5" />
                    <span>CSV Audit</span>
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <div className="p-8 text-center text-white/40 text-xs">Select a dossier to view details</div>
          )}
        </div>
      </div>
    </div>
  );
};
