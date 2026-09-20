import React, { useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import FinancialAnalysisResult from '../../../pages/Finance/FinancialAnalysisResult';

export default function ReportingAnalysisResultPage() {
  const { taskId } = useParams<{ taskId: string }>();
  const navigate = useNavigate();

  useEffect(() => {
    const orig = window.history.pushState.bind(window.history);
    const pushState: History['pushState'] = (state, title, url) => {
      if (typeof url === 'string') {
        const m = url.match(/^\/finance\/trace\/([^/?#]+)/);
        if (m) {
          navigate(`/finance/reporting/traces/${m[1]}`);
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

  if (!taskId) {
    return <p>Missing task id.</p>;
  }

  return (
    <div>
      <h1 className='finance-page-title'>Analysis result</h1>
      <p className='finance-page-lede'>Task {taskId}</p>
      <FinancialAnalysisResult />
    </div>
  );
}
