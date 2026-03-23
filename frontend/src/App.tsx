import { Navigate, Route, Routes } from 'react-router-dom'

import { DashboardPage } from './features/dashboard/DashboardPage.tsx'
import { TroubleshootingShellPage } from './features/troubleshooting/TroubleshootingShellPage.tsx'
import { WizardShellPage } from './features/wizard/WizardShellPage.tsx'
import { AppFrame } from './shared/components/AppFrame.tsx'

export default function App() {
  return (
    <Routes>
      <Route element={<AppFrame />}>
        <Route index element={<Navigate replace to="/dashboard" />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/wizard" element={<WizardShellPage />} />
        <Route path="/troubleshooting" element={<TroubleshootingShellPage />} />
        <Route path="/app" element={<Navigate replace to="/dashboard" />} />
        <Route path="/app/dashboard" element={<Navigate replace to="/dashboard" />} />
        <Route path="/app/wizard" element={<Navigate replace to="/wizard" />} />
        <Route path="/app/troubleshooting" element={<Navigate replace to="/troubleshooting" />} />
      </Route>
    </Routes>
  )
}
