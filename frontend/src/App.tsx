import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { Stack } from '@mui/material'
import { AppShell } from './components/AppShell'
import { HomePage } from './pages/HomePage'
import { LoginPage } from './pages/LoginPage'
import { RegisterPage } from './pages/RegisterPage'
import { RegistrationStatusPage } from './pages/RegistrationStatusPage'
import { AdminPortalPage } from './pages/AdminPortalPage'
import { AnalyzerPage } from './pages/AnalyzerPage'
import { CatalogExplorerPage } from './pages/CatalogExplorerPage'
import { ReviewerDashboardPage } from './pages/ReviewerDashboardPage'
import { ChangePasswordPage } from './pages/ChangePasswordPage'
import { ForgotPasswordPage } from './pages/ForgotPasswordPage'
import type { User } from './types'
import { api } from './api'
import { homePathForUser } from './utils/homePath'

function readStoredUser(): User | null {
  const raw = localStorage.getItem('user')
  if (!raw) return null
  try {
    return JSON.parse(raw) as User
  } catch {
    return null
  }
}

export default function App() {
  const [user, setUser] = useState<User | null>(() => readStoredUser())
  const isAuthed = useMemo(() => Boolean(user && localStorage.getItem('access_token')), [user])
  const isActive = user?.status === 'active'
  const mustChangePassword = Boolean(user?.must_change_password)

  // Refresh /me so stale localStorage (must_change_password) cannot trap the user.
  useEffect(() => {
    if (!localStorage.getItem('access_token')) return
    void api
      .get<User>('/api/v1/auth/me')
      .then((res) => {
        localStorage.setItem('user', JSON.stringify(res.data))
        setUser(res.data)
      })
      .catch(() => {
        /* keep stored user; login flow will recover */
      })
  }, [])

  const logout = async () => {
    const refresh = localStorage.getItem('refresh_token')
    try {
      if (refresh) await api.post('/api/v1/auth/logout', { refresh_token: refresh })
    } catch {
      /* ignore */
    }
    localStorage.clear()
    setUser(null)
  }

  const handleLogin = (next: User) => {
    setUser(next)
  }

  const gateActive = (node: ReactNode) => {
    if (!isAuthed || !user) return <Navigate to="/login" replace />
    if (mustChangePassword) return <Navigate to="/change-password" replace />
    if (user.status !== 'active') return <Navigate to="/registration-status" replace />
    return node
  }

  const authedHome = user ? homePathForUser(user) : '/'

  return (
    <AppShell>
      <Routes>
        <Route
          path="/login"
          element={
            isAuthed && isActive && !mustChangePassword ? (
              <Navigate to={authedHome} replace />
            ) : isAuthed && mustChangePassword ? (
              <Navigate to="/change-password" replace />
            ) : (
              <LoginPage onLogin={handleLogin} />
            )
          }
        />
        <Route path="/register" element={<RegisterPage onLogin={handleLogin} />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route
          path="/registration-status"
          element={<RegistrationStatusPage user={user} onUserUpdate={handleLogin} />}
        />
        <Route
          path="/change-password"
          element={
            isAuthed && user ? (
              <ChangePasswordPage user={user} onChanged={handleLogin} />
            ) : (
              <Navigate to="/login" replace />
            )
          }
        />

        <Route
          path="/"
          element={gateActive(
            user?.role === 'administrator' ? (
              <Navigate to="/admin" replace />
            ) : user?.role === 'pharmacist' ? (
              <Navigate to="/analyzer" replace />
            ) : user?.role === 'reviewer' ? (
              <Navigate to="/research/evaluation" replace />
            ) : (
              <Stack spacing={2}>
                <HomePage user={user!} onLogout={logout} />
              </Stack>
            ),
          )}
        />

        <Route
          path="/admin"
          element={gateActive(
            user?.role === 'administrator' ? (
              <AdminPortalPage onLogout={logout} />
            ) : (
              <Navigate to={authedHome} replace />
            ),
          )}
        />
        <Route
          path="/admin/registrations"
          element={gateActive(
            user?.role === 'administrator' ? (
              <Navigate to="/admin?tab=registrations" replace />
            ) : (
              <Navigate to={authedHome} replace />
            ),
          )}
        />
        <Route
          path="/analyzer"
          element={gateActive(
            user?.role === 'pharmacist' ? (
              <AnalyzerPage onLogout={logout} />
            ) : (
              <Navigate to={authedHome} replace />
            ),
          )}
        />

        <Route
          path="/catalog"
          element={gateActive(
            user?.role === 'pharmacist' ? (
              <CatalogExplorerPage onLogout={logout} />
            ) : (
              <Navigate to={authedHome} replace />
            ),
          )}
        />

        <Route
          path="/research/evaluation"
          element={gateActive(
            user?.role === 'reviewer' ? (
              <ReviewerDashboardPage onLogout={logout} />
            ) : (
              <Navigate to={authedHome} replace />
            ),
          )}
        />

        <Route
          path="*"
          element={
            <Navigate
              to={
                !isAuthed
                  ? '/login'
                  : mustChangePassword
                    ? '/change-password'
                    : user
                      ? homePathForUser(user)
                      : '/'
              }
              replace
            />
          }
        />
      </Routes>
    </AppShell>
  )
}
