/**
 * Admin Monitor — embeds the slim ops Monitor (Status / Now / Pulse / Actions + Grafana).
 * ShellStatusProvider is required by MonitorPage (normally provided by MainLayout).
 */
import React from 'react';
import MonitorPage from '../../../pages/Monitor/MonitorPage';
import { ShellStatusProvider } from '../../../contexts/ShellStatusContext';

export default function AdminMonitorPage() {
  return (
    <ShellStatusProvider>
      <div className='admin-monitor-embed'>
        <MonitorPage />
      </div>
    </ShellStatusProvider>
  );
}
