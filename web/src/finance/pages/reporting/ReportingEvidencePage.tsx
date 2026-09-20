import React from 'react';
import EvidenceExplorer from '../../../pages/Finance/EvidenceExplorer';

export default function ReportingEvidencePage() {
  return (
    <div>
      <h1 className='finance-page-title'>Evidence</h1>
      <p className='finance-page-lede'>
        Evidence ledger index for finance analysis provenance (FRED / EDGAR / gold refs).
      </p>
      <EvidenceExplorer />
    </div>
  );
}
