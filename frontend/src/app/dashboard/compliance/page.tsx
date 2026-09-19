'use client';

import React, { useState } from 'react';
import { ReportsView } from '@/components/vigil/ReportsView';
import { COMPLIANCE_REPORTS } from '@/data/vigilData';
import { ComplianceReport } from '@/lib/types';

export default function DashboardCompliancePage() {
  const [reports] = useState<ComplianceReport[]>(COMPLIANCE_REPORTS);

  const handleDownloadReport = (
    reportId: string,
    format: 'pdf' | 'sarif' | 'csv'
  ) => {
    const report = reports.find((r) => r.id === reportId) || reports[0];
    const dataStr =
      'data:text/json;charset=utf-8,' +
      encodeURIComponent(
        JSON.stringify(
          {
            reportId: report.id,
            title: report.title,
            framework: report.framework,
            sha256Digest: report.sha256Digest,
            downloadedAt: new Date().toISOString(),
            status: report.status,
            format,
          },
          null,
          2
        )
      );
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute('href', dataStr);
    downloadAnchor.setAttribute(
      'download',
      `vigil-${report.id}.${format === 'sarif' ? 'sarif.json' : format}`
    );
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  return (
    <ReportsView
      reports={reports}
      onDownloadReport={handleDownloadReport}
    />
  );
}
