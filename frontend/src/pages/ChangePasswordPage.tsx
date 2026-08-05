import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { zodResolver } from '@hookform/resolvers/zod'
import { Alert, Box, Button, Card, CardContent, Stack, TextField, Typography } from '@mui/material'
import { api } from '../api'
import type { User } from '../types'
import { homePathForUser } from '../utils/homePath'

const schema = z
  .object({
    current_password: z.string().min(1, 'Current password is required'),
    new_password: z
      .string()
      .min(12, 'At least 12 characters')
      .refine((v) => /[a-z]/.test(v) && /[A-Z]/.test(v) && /\d/.test(v), {
        message: 'Include upper, lower, and a digit',
      }),
    confirm_password: z.string().min(1, 'Confirm the new password'),
  })
  .refine((v) => v.new_password === v.confirm_password, {
    message: 'Passwords do not match',
    path: ['confirm_password'],
  })
  .refine((v) => v.current_password !== v.new_password, {
    message: 'New password must differ from the current password',
    path: ['new_password'],
  })

type FormValues = z.infer<typeof schema>

export function ChangePasswordPage({
  user,
  onChanged,
}: {
  user: User
  onChanged: (next: User) => void
}) {
  const navigate = useNavigate()
  const [error, setError] = useState('')
  const [checking, setChecking] = useState(true)
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { current_password: '', new_password: '', confirm_password: '' },
  })

  // Stale localStorage can keep must_change_password=true after the DB flag is cleared.
  useEffect(() => {
    let cancelled = false
    void api
      .get<User>('/api/v1/auth/me')
      .then((res) => {
        if (cancelled) return
        localStorage.setItem('user', JSON.stringify(res.data))
        onChanged(res.data)
        if (!res.data.must_change_password) {
          navigate(homePathForUser(res.data), { replace: true })
        }
      })
      .catch(() => {
        /* keep form if /me fails */
      })
      .finally(() => {
        if (!cancelled) setChecking(false)
      })
    return () => {
      cancelled = true
    }
  }, [navigate, onChanged])

  const onSubmit = async (values: FormValues) => {
    setError('')
    try {
      const { data } = await api.post<User>('/api/v1/auth/change-password', {
        current_password: values.current_password,
        new_password: values.new_password,
      })
      localStorage.setItem('user', JSON.stringify(data))
      onChanged(data)
      navigate(homePathForUser(data))
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number; data?: { detail?: string } } })?.response
        ?.status
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      if (status === 404) {
        setError(
          'Change-password API not found. Restart the backend (uvicorn) so award-path routes are loaded, then try again — or use Continue below after restart.',
        )
      } else {
        setError(typeof detail === 'string' ? detail : 'Could not change password. Try again.')
      }
    }
  }

  const continueWithoutChange = async () => {
    setError('')
    try {
      const { data } = await api.get<User>('/api/v1/auth/me')
      localStorage.setItem('user', JSON.stringify(data))
      onChanged(data)
      if (data.must_change_password) {
        setError('Server still requires a password change. Set a new password below, or ask to clear the flag.')
        return
      }
      navigate(homePathForUser(data), { replace: true })
    } catch {
      setError('Could not refresh session. Log out and sign in again.')
    }
  }

  if (checking) {
    return (
      <Card sx={{ maxWidth: 480, mx: 'auto' }}>
        <CardContent>
          <Typography color="text.secondary">Checking account status…</Typography>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card sx={{ maxWidth: 480, mx: 'auto' }}>
      <CardContent>
        <Typography variant="h4" gutterBottom>
          Change password
        </Typography>
        <Typography color="text.secondary" mb={2}>
          Account <strong>{user.username}</strong>
          {user.must_change_password
            ? ' — set a personal password before continuing (research security posture).'
            : ' — password change is optional for this account.'}
        </Typography>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}
        <Box component="form" onSubmit={handleSubmit(onSubmit)}>
          <Stack spacing={2}>
            <TextField
              label="Current password"
              type="password"
              autoComplete="current-password"
              error={!!errors.current_password}
              helperText={errors.current_password?.message}
              {...register('current_password')}
            />
            <TextField
              label="New password"
              type="password"
              autoComplete="new-password"
              error={!!errors.new_password}
              helperText={errors.new_password?.message || 'Min 12 chars · upper + lower + digit'}
              {...register('new_password')}
            />
            <TextField
              label="Confirm new password"
              type="password"
              autoComplete="new-password"
              error={!!errors.confirm_password}
              helperText={errors.confirm_password?.message}
              {...register('confirm_password')}
            />
            <Button type="submit" variant="contained" disabled={isSubmitting}>
              {isSubmitting ? 'Saving…' : 'Save new password'}
            </Button>
            <Button type="button" variant="outlined" onClick={() => void continueWithoutChange()}>
              Continue to app
            </Button>
            <Button type="button" color="inherit" onClick={() => {
              localStorage.clear()
              navigate('/login', { replace: true })
              window.location.reload()
            }}>
              Log out
            </Button>
          </Stack>
        </Box>
      </CardContent>
    </Card>
  )
}
