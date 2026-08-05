import { useState } from 'react'
import { Alert, Button, Card, CardContent, Chip, Stack, Typography } from '@mui/material'
import { Link as RouterLink, useLocation, useNavigate } from 'react-router-dom'
import { api } from '../api'
import type { User } from '../types'
import { homePathForUser } from '../utils/homePath'

function statusCopy(status: string, justRegistered: boolean): { severity: 'success' | 'info' | 'warning' | 'error'; text: string } {
  if (status === 'active') {
    return {
      severity: 'success',
      text: 'Your account is active. You may use role-appropriate features such as the Prescription Analyzer.',
    }
  }
  if (status === 'inactive') {
    return {
      severity: 'error',
      text: 'Your registration was rejected or your account is inactive. Contact an administrator if you believe this is incorrect.',
    }
  }
  if (status === 'locked') {
    return {
      severity: 'warning',
      text: 'Your account is temporarily locked. Try again later or contact an administrator.',
    }
  }
  return {
    severity: 'info',
    text: justRegistered
      ? 'Registration submitted. Your account is awaiting administrator approval. Clinical features stay locked until then.'
      : 'Your registration is awaiting administrator approval. You can refresh this page after an administrator reviews your request.',
  }
}

export function RegistrationStatusPage({
  user,
  onUserUpdate,
}: {
  user: User | null
  onUserUpdate?: (user: User) => void
}) {
  const location = useLocation()
  const navigate = useNavigate()
  const state = (location.state as { username?: string; justRegistered?: boolean } | null) || null
  const username = user?.username || state?.username
  const status = user?.status || 'pending'
  const justRegistered = Boolean(state?.justRegistered)
  const copy = statusCopy(status, justRegistered)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const refreshStatus = async () => {
    setError('')
    setBusy(true)
    try {
      const { data } = await api.get<User>('/api/v1/auth/me')
      localStorage.setItem('user', JSON.stringify(data))
      onUserUpdate?.(data)
      if (data.status === 'active' && !data.must_change_password) {
        navigate(homePathForUser(data), { replace: true })
      }
    } catch {
      setError('Could not refresh status. Sign in again if your session expired.')
    } finally {
      setBusy(false)
    }
  }

  const chipColor =
    status === 'active' ? 'success' : status === 'inactive' ? 'error' : 'warning'

  return (
    <Card>
      <CardContent>
        <Typography variant="h4" gutterBottom>
          Registration status
        </Typography>
        {username && (
          <Typography color="text.secondary" mb={1}>
            Username: {username}
          </Typography>
        )}
        <Chip
          label={status.replaceAll('_', ' ')}
          color={chipColor}
          sx={{ mb: 2, textTransform: 'capitalize' }}
        />
        <Alert severity={copy.severity} sx={{ mb: 2 }}>
          {copy.text}
        </Alert>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1}>
          {user && status !== 'active' && (
            <Button variant="contained" disabled={busy} onClick={() => void refreshStatus()}>
              {busy ? 'Refreshing…' : 'Refresh status'}
            </Button>
          )}
          {status === 'active' && user && (
            <Button component={RouterLink} to={homePathForUser(user)} variant="contained">
              Continue
            </Button>
          )}
          <Button component={RouterLink} to="/login" variant={user ? 'outlined' : 'contained'}>
            {user ? 'Back to login' : 'Go to login'}
          </Button>
        </Stack>
      </CardContent>
    </Card>
  )
}
