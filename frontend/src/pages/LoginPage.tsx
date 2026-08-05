import { useState } from 'react'
import { Link as RouterLink, useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { zodResolver } from '@hookform/resolvers/zod'
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Checkbox,
  FormControlLabel,
  Link,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import { api } from '../api'
import type { LoginResponse, User } from '../types'
import { homePathForUser } from '../utils/homePath'

const schema = z.object({
  username: z.string().min(1, 'Username is required'),
  password: z.string().min(1, 'Password is required'),
  remember: z.boolean().optional(),
})

type FormValues = z.infer<typeof schema>

export function LoginPage({ onLogin }: { onLogin: (user: User) => void }) {
  const navigate = useNavigate()
  const [error, setError] = useState('')
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { username: '', password: '', remember: true },
  })

  const onSubmit = async (values: FormValues) => {
    setError('')
    try {
      const { data } = await api.post<LoginResponse>('/api/v1/auth/login', {
        username: values.username,
        password: values.password,
      })
      localStorage.setItem('access_token', data.access_token)
      localStorage.setItem('refresh_token', data.refresh_token)
      localStorage.setItem('user', JSON.stringify(data.user))
      onLogin(data.user)
      if (data.user.must_change_password) {
        navigate('/change-password')
      } else {
        navigate(homePathForUser(data.user))
      }
    } catch {
      setError('We could not sign you in. Check your username and password and try again.')
    }
  }

  return (
    <Card>
      <CardContent>
        <Typography variant="h4" gutterBottom>
          Sign in
        </Typography>
        <Typography color="text.secondary" mb={3}>
          Access the PharmaAssist research prototype.
        </Typography>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        <Box component="form" onSubmit={handleSubmit(onSubmit)}>
          <Stack spacing={2}>
            <TextField
              label="Username or User ID"
              autoComplete="username"
              error={!!errors.username}
              helperText={errors.username?.message}
              {...register('username')}
            />
            <TextField
              label="Password"
              type="password"
              autoComplete="current-password"
              error={!!errors.password}
              helperText={errors.password?.message}
              {...register('password')}
            />
            <FormControlLabel
              control={<Checkbox defaultChecked {...register('remember')} />}
              label="Remember this device"
            />
            <Button type="submit" variant="contained" disabled={isSubmitting}>
              {isSubmitting ? 'Signing in…' : 'Login'}
            </Button>
            <Typography variant="body2">
              <RouterLink to="/register">Register as a pharmacist</RouterLink>
            </Typography>
            <Typography variant="body2" color="text.secondary">
              New pharmacists must register and wait for administrator approval before using the
              Prescription Analyzer.
            </Typography>
            <Typography variant="body2">
              <RouterLink to="/forgot-password">Forgot password?</RouterLink>
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Administrator and Reviewer accounts are created by an Administrator.
            </Typography>
            <Link href="http://127.0.0.1:8000/docs" target="_blank" rel="noreferrer">
              API docs
            </Link>
          </Stack>
        </Box>
      </CardContent>
    </Card>
  )
}
