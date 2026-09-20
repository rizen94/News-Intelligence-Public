import React from 'react';
import { Link, useParams } from 'react-router-dom';
import TaskTraceViewer from '../../../pages/Finance/TaskTraceViewer';

export default function ReportingTracesPage() {
  const { taskId } = useParams<{ taskId?: string }>();

  if (!taskId) {
    return (
      <div>
        <h1 className='finance-page-title'>Traces</h1>
        <p className='finance-page-lede'>
          Open a completed analysis task to view its span-level trace. From an analysis result,
          use the Trace action, or go to{' '}
          <code>/finance/reporting/traces/:taskId</code>.
        </p>
        <p>
          Start from <Link to='/finance/reporting/analysis'>Analysis</Link>, or use the classic
          path <code>/finance/trace/:taskId</code>.
        </p>
      </div>
    );
  }

  return (
    <div>
      <h1 className='finance-page-title'>Task trace</h1>
      <p className='finance-page-lede'>Task {taskId}</p>
      <TaskTraceViewer />
    </div>
  );
}
