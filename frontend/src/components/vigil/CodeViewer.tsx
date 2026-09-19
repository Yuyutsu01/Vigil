'use client';

import React, { useEffect, useRef } from 'react';
import { Copy, Check, FileCode } from 'lucide-react';
import { Finding } from '@/lib/types';
import { focusRing } from '@/lib/styles';

interface CodeViewerProps {
  code: string;
  language: string;
  fileName: string;
  findings: Finding[];
  selectedFindingId: string | null;
  onSelectFinding: (id: string) => void;
}

export const CodeViewer: React.FC<CodeViewerProps> = ({
  code,
  language,
  fileName,
  findings,
  selectedFindingId,
  onSelectFinding,
}) => {
  const [copied, setCopied] = React.useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const lines = code.split('\n');

  const lineFindingMap = React.useMemo(() => {
    const map = new Map<number, Finding>();
    findings.forEach((f) => {
      for (let l = f.line; l <= (f.endLine || f.line); l++) {
        map.set(l, f);
      }
    });
    return map;
  }, [findings]);

  const selectedFinding = findings.find((f) => f.id === selectedFindingId);

  useEffect(() => {
    if (selectedFinding && containerRef.current) {
      const lineElement = containerRef.current.querySelector(
        `[data-line="${selectedFinding.line}"]`
      );
      if (lineElement) {
        lineElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }
  }, [selectedFinding]);

  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="flex flex-col h-full bg-black border-r border-white/10 text-white select-none">
      {/* File Header */}
      <div className="h-10 px-4 border-b border-white/10 bg-black flex items-center justify-between text-xs shrink-0">
        <div className="flex items-center gap-2 font-mono text-white/70 truncate">
          <FileCode className="w-3.5 h-3.5 text-white/50" />
          <span className="font-semibold text-white truncate">{fileName}</span>
          <span className="text-[10.5px] px-1.5 py-0.2 rounded-full bg-white/10 text-white/80 uppercase">
            {language}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleCopy}
            aria-label={copied ? 'Copied' : 'Copy code'}
            className={`p-1 rounded-full hover:bg-white/10 text-white/50 hover:text-white transition-colors flex items-center gap-1 text-[11px] cursor-pointer ${focusRing}`}
            title="Copy code to clipboard"
          >
            {copied ? (
              <>
                <Check className="w-3.5 h-3.5 text-emerald-400" />
                <span className="text-emerald-400">Copied</span>
              </>
            ) : (
              <>
                <Copy className="w-3.5 h-3.5" />
                <span>Copy</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Code Area with Line Numbers */}
      <div
        ref={containerRef}
        className="flex-1 overflow-auto p-2 font-mono text-[12px] leading-relaxed select-text"
        style={{ fontFamily: "'JetBrains Mono', 'Fira Code', Menlo, Consolas, monospace" }}
      >
        <div className="table w-full">
          {lines.map((lineContent, idx) => {
            const lineNum = idx + 1;
            const findingOnLine = lineFindingMap.get(lineNum);
            const isSelected = selectedFinding && selectedFinding.line === lineNum;
            let highlightBg = '';
            let lineIndicator = '';

            if (findingOnLine) {
              if (findingOnLine.severity === 'critical') {
                highlightBg = isSelected
                  ? 'bg-red-500/25 border-l-2 border-red-500 text-red-200 font-medium'
                  : 'bg-red-500/10 border-l-2 border-red-500/60 text-white';
                lineIndicator = 'text-red-400 font-bold';
              } else if (findingOnLine.severity === 'high') {
                highlightBg = isSelected
                  ? 'bg-orange-500/25 border-l-2 border-orange-500 text-orange-200 font-medium'
                  : 'bg-orange-500/10 border-l-2 border-orange-500/60 text-white';
                lineIndicator = 'text-orange-400 font-bold';
              } else if (findingOnLine.severity === 'medium') {
                highlightBg = isSelected
                  ? 'bg-amber-500/25 border-l-2 border-amber-500 text-amber-200 font-medium'
                  : 'bg-amber-500/10 border-l-2 border-amber-500/60 text-white';
                lineIndicator = 'text-amber-400 font-bold';
              } else {
                highlightBg = isSelected
                  ? 'bg-blue-500/25 border-l-2 border-blue-500 text-blue-200 font-medium'
                  : 'bg-blue-500/10 border-l-2 border-blue-500/60 text-white';
                lineIndicator = 'text-blue-400 font-bold';
              }
            } else if (isSelected) {
              highlightBg = 'bg-white/10';
            }

            return (
              <div
                key={lineNum}
                data-line={lineNum}
                onClick={() => {
                  if (findingOnLine) onSelectFinding(findingOnLine.id);
                }}
                className={`table-row transition-colors group ${highlightBg} ${
                  findingOnLine ? 'cursor-pointer' : ''
                }`}
              >
                <div
                  className={`table-cell pr-4 pl-2 text-right select-none text-[11px] w-12 shrink-0 ${
                    lineIndicator || 'text-white/30 group-hover:text-white/60'
                  }`}
                >
                  {lineNum}
                </div>
                <div className="table-cell pr-4 whitespace-pre text-white/80">
                  {lineContent || '\u00A0'}
                </div>
                {findingOnLine && findingOnLine.line === lineNum && (
                  <div className="table-cell pr-2 text-right select-none">
                    <span
                      className={`inline-block px-1.5 py-0.2 rounded text-[10px] uppercase font-bold tracking-wider ${
                        findingOnLine.severity === 'critical'
                          ? 'bg-red-500/30 text-red-300'
                          : findingOnLine.severity === 'high'
                          ? 'bg-orange-500/30 text-orange-300'
                          : 'bg-amber-500/30 text-amber-300'
                      }`}
                    >
                      {findingOnLine.cwe || findingOnLine.severity}
                    </span>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      <div className="h-7 px-4 border-t border-white/10 bg-black flex items-center justify-between text-[11px] text-white/40 select-none font-mono">
        <div>
          <span>{lines.length} lines</span> • <span>UTF-8</span>
        </div>
        <div className="flex items-center gap-2">
          <span>{findings.length} flagged security nodes</span>
        </div>
      </div>
    </div>
  );
};
