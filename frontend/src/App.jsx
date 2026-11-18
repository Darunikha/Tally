import { Navigate, Route, Routes } from 'react-router-dom'
import AppLayout from './components/layout/AppLayout'
import { Spinner } from './components/ui'
import { useAuth } from './context/AuthContext'
import { FilterProvider } from './context/FilterContext'
import Analytics from './pages/Analytics'
import Anomalies from './pages/Anomalies'
import Budgets from './pages/Budgets'
import { ForgotPassword, Login, Register, ResetPassword, VerifyEmail } from './pages/Auth'
import { PrivacyPolicy, Terms } from './pages/Legal'
import CategoriesRules from './pages/CategoriesRules'
import Dashboard from './pages/Dashboard'
import SettingsPage from './pages/Settings'
import StatementHistory from './pages/StatementHistory'
import Transactions from './pages/Transactions'
import UpiAnalysis from './pages/UpiAnalysis'
import Upload from './pages/Upload'

function Protected({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="grid min-h-screen place-items-center"><Spinner className="h-8 w-8" /></div>
  if (!user) return <Navigate to="/login" replace />
  return <FilterProvider>{children}</FilterProvider>
}

function PublicOnly({ children }) {
  const { user, loading } = useAuth()
  if (loading) return null
  return user ? <Navigate to="/" replace /> : children
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<PublicOnly><Login /></PublicOnly>} />
      <Route path="/register" element={<PublicOnly><Register /></PublicOnly>} />
      <Route path="/forgot-password" element={<PublicOnly><ForgotPassword /></PublicOnly>} />
      <Route path="/reset-password" element={<ResetPassword />} />
      <Route path="/verify-email" element={<VerifyEmail />} />
      <Route path="/privacy" element={<PrivacyPolicy />} />
      <Route path="/terms" element={<Terms />} />
      <Route element={<Protected><AppLayout /></Protected>}>
        <Route index element={<Dashboard />} />
        <Route path="upload" element={<Upload />} />
        <Route path="transactions" element={<Transactions />} />
        <Route path="upi" element={<UpiAnalysis />} />
        <Route path="analytics" element={<Analytics />} />
        <Route path="anomalies" element={<Anomalies />} />
        <Route path="budgets" element={<Budgets />} />
        <Route path="categories" element={<CategoriesRules />} />
        <Route path="statements" element={<StatementHistory />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
