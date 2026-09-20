/**
 * Reporting analysis shell — wraps classic FinancialAnalysis with Finance product paths.
 */
import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import FinancialAnalysis from '../../../pages/Finance/FinancialAnalysis';

/**
 * Classic FinancialAnalysis navigates to /{domain}/analysis/:id.
 * Intercept via history patch is fragile; instead we render it and document that
 * deep-links also exist under /finance/reporting/analysis/:taskId which remounts
 * the result viewer.
 */
export default function ReportingAnalysisPage() {
  const navigate = useNavigate();

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement | null;
      const anchor = target?.closest?.('a[href]') as HTMLAnchorElement | null;
      if (!anchor) return;
      const href = anchor.getAttribute('href') || '';
      const m = href.match(/^\/finance\/analysis\/([^/?#]+)/);
      if (m) {
        e.preventDefault();
        navigate(`/finance/reporting/analysis/${m[1]}`);
      }
    };
    document.addEventListener('click', onClick);
    return () => document.removeEventListener('click', onClick);
  }, [navigate]);

  useEffect(() => {
    const orig = window.history.pushState.bind(window.history);
    // Catch SPA navigations to classic /finance/analysis/:id from the wrapped page
    const pushState: History['pushState'] = (state, title, url) => {
      if (typeof url === 'string') {
        const m = url.match(/^\/finance\/analysis\/([^/?#]+)/);
        if (m) {
          navigate(`/finance/reporting/analysis/${m[1]}`);
          return;
        }
      }
      return orig(state, title, url);
    };
    window.history.pushState = pushState;
    return () => {
      window.history.pushState = orig;
    };
  }, [navigate]);

  return (
    <div>
      <h1 className='finance-page-title'>Analysis</h1>
      <p className='finance-page-lede'>
        Submit finance research tasks. Results open under{' '}
        <code>/finance/reporting/analysis/:taskId</code>. Classic{' '}
        <code>/finance/analysis</code> remains available.
      </p>
      <FinancialAnalysis />
    </div>
  );
}
