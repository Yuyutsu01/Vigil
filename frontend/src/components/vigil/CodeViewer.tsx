'use client';

import React, { useEffect, useRef } from 'react';
import { Copy, Check, FileCode, Maximize } from 'lucide-react';
import { Finding, Review } from '@/lib/types';
import { focusRing } from '@/lib/styles';

interface CodeViewerProps {
  code: string;
  language: string;
  fileName: string;
  findings: Finding[];
  selectedFindingId: string | null;
  onSelectFinding: (id: string) => void;
  review?: Review;
}

export const CodeViewer: React.FC<CodeViewerProps> = ({
  code,
  language,
  fileName,
  findings,
  selectedFindingId,
  onSelectFinding,
  review,
}) => {
  const [copied, setCopied] = React.useState(false);
  const [selectedLang, setSelectedLang] = React.useState(language);
  const containerRef = useRef<HTMLDivElement>(null);
  const lines = code.split('\n');

  const REPO_REVIEW_PLACEHOLDER = '[REPOSITORY_REVIEW_MEMORY_ONLY]';
  const isRepoReview =
    code === REPO_REVIEW_PLACEHOLDER ||
    code.includes('REPOSITORY_REVIEW_MEMORY_ONLY');

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
    if (selectedFinding && containerRef.current && !isRepoReview) {
      const lineElement = containerRef.current.querySelector(
        `[data-line="${selectedFinding.line}"]`
      );
      if (lineElement) {
        lineElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }
  }, [selectedFinding, isRepoReview]);

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
          <select 
            value={selectedLang}
            onChange={(e) => setSelectedLang(e.target.value)}
            className="text-[10.5px] px-1.5 py-0.5 rounded-sm bg-white/10 text-white/80 uppercase outline-none border-none cursor-pointer hover:bg-white/20 appearance-none"
          >
            <option value="python">PYTHON</option>
            <option value="typescript">TYPESCRIPT</option>
            <option value="javascript">JAVASCRIPT</option>
            <option value="go">GO</option>
            <option value="rust">RUST</option>
          </select>
        </div>
        {!isRepoReview && (
          <div className="flex items-center gap-2">
            <button
              aria-label="Full screen"
              className={`p-1 rounded-full hover:bg-white/10 text-white/50 hover:text-white transition-colors flex items-center gap-1 text-[11px] cursor-pointer ${focusRing}`}
              title="Toggle Full Screen"
            >
              <Maximize className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={handleCopy}
              aria-label={copied ? 'Copied' : 'Copy code'}
              className={`p-1 rounded-full hover:bg-white/10 text-white/50 hover:text-white transition-colors flex items-center gap-1 text-[11px] cursor-pointer ${focusRing}`}
              title="Copy code to clipboard"
            >
              {copied ? (
                <>
                  <Check className="w-3.5 h-3.5 text-white/60" />
                  <span className="text-white/60">Copied</span>
                </>
              ) : (
                <>
                  <Copy className="w-3.5 h-3.5" />
                  <span>Copy</span>
                </>
              )}
            </button>
          </div>
        )}
      </div>

      {/* Code Area with Line Numbers */}
      <div
        ref={containerRef}
        className="flex-1 overflow-auto p-2 font-mono text-[12px] leading-relaxed select-text"
        style={{ fontFamily: "'JetBrains Mono', 'Fira Code', Menlo, Consolas, monospace" }}
      >
        {isRepoReview ? (
          <div className="p-8 text-center border border-white/10 rounded-lg bg-white/[0.02] m-2">
            <FileCode className="w-8 h-8 mx-auto text-white/40" />
            <h3 className="mt-3 text-sm font-semibold text-white">
              Source code was not persisted
            </h3>
            <p className="mt-2 text-xs text-white/60 max-w-md mx-auto">
              For repository reviews, Vigil reads source files from GitHub
              on demand and discards them after analysis. The findings below
              reference the exact file and line for each issue.
            </p>
            {review?.repoFullName && review?.refValue && (
              <a
                href={`https://github.com/${review.repoFullName}/blob/${review.refValue}`}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-block mt-4 px-3 py-1.5 text-xs rounded-lg bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-300 border border-cyan-500/30"
              >
                View repository on GitHub →
              </a>
            )}
          </div>
        ) : (
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
        )}
      </div>

      <div className="h-7 px-4 border-t border-white/10 bg-black flex items-center justify-between text-[11px] text-white/40 select-none font-mono">
        <div>
          {isRepoReview ? (
            <span>GitHub Repository Scan</span>
          ) : (
            <>
              <span>{lines.length} lines</span> • <span>UTF-8</span>
            </>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span>{findings.length} flagged security nodes</span>
        </div>
      </div>
    </div>
  );
};
