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
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import { api } from '../api'

const schema = z.object({
  username: z.string().min(1, 'Username is required'),
})

type FormValues = z.infer<typeof schema>

type ForgotResponse = {
  message: string
  temporary_password: string | null
}

export function ForgotPasswordPage() {
  const navigate = useNavigate()
  const [error, setError] = useState('')
  const [result, setResult] = useState<ForgotResponse | null>(null)
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { username: '' },
  })

  const onSubmit = async (values: FormValues) => {
    setError('')
    setResult(null)
    try {
      const { data } = await api.post<ForgotResponse>('/api/v1/auth/forgot-password', {
        username: values.username.trim(),
      })
      setResult(data)
    } catch {
      setError('Could not process the reset request. Try again shortly.')
    }
  }

  return (
    <Card>
      <CardContent>
        <Typography variant="h4" gutterBottom>
          Forgot password
        </Typography>
        <Typography color="text.secondary" mb={3}>
          Enter your username. For this research prototype there is no email delivery — a temporary
          password is shown once so you can sign in and choose a new one.
        </Typography>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        {result?.temporary_password ? (
          <Stack spacing={2}>
            <Alert severity="success">{result.message}</Alert>
            <Alert severity="warning">
              Temporary password (copy now):{' '}
              <Typography component="span" fontFamily="monospace" fontWeight={700}>
                {result.temporary_password}
              </Typography>
            </Alert>
            <Button variant="contained" onClick={() => navigate('/login')}>
              Go to sign in
            </Button>
          </Stack>
        ) : (
          <Box component="form" onSubmit={handleSubmit(onSubmit)}>
            <Stack spacing={2}>
              {result && !result.temporary_password && (
                <Alert severity="info">{result.message}</Alert>
              )}
              <TextField
                label="Username"
                autoComplete="username"
                error={!!errors.username}
                helperText={errors.username?.message}
                {...register('username')}
              />
              <Button type="submit" variant="contained" disabled={isSubmitting}>
                {isSubmitting ? 'Requesting…' : 'Reset password'}
              </Button>
              <Typography variant="body2">
                <RouterLink to="/login">Back to sign in</RouterLink>
              </Typography>
            </Stack>
          </Box>
        )}
      </CardContent>
    </Card>
  )
}
