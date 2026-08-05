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
  List,
  ListItem,
  Stack,
  Step,
  StepLabel,
  Stepper,
  TextField,
  Typography,
} from '@mui/material'
import { api } from '../api'
import type { LoginResponse, User } from '../types'
import {
  DOCUMENT_DATE,
  DOCUMENT_VERSION,
  ELECTRONIC_AFFIRMATION,
  PIS_ACK_LABEL,
  consentStatements,
  pisText,
} from '../content/researchDocuments'

const WEAK_SUBSTRINGS = ['password', '123456', 'pharmaassist', 'liverpool']

function passwordPolicyMessage(password: string, username: string): string | null {
  if (password.length < 12) return 'Password must be at least 12 characters'
  if (username && password.toLowerCase() === username.toLowerCase()) {
    return 'Password must not match the username'
  }
  const lowered = password.toLowerCase()
  if (WEAK_SUBSTRINGS.some((s) => lowered.includes(s))) {
    return 'Password is too weak — avoid common words like password / 123456'
  }
  const classes = [
    /[a-z]/.test(password),
    /[A-Z]/.test(password),
    /\d/.test(password),
    /[^A-Za-z0-9]/.test(password),
  ].filter(Boolean).length
  if (classes < 3) {
    return 'Password needs at least 3 of: lower, upper, digit, symbol'
  }
  return null
}

const accountSchema = z
  .object({
    pharmacist_registration_id: z.string().min(3),
    username: z.string().min(3),
    password: z.string().min(12),
    confirm: z.string(),
    adult: z.literal(true),
  })
  .superRefine((v, ctx) => {
    const msg = passwordPolicyMessage(v.password, v.username)
    if (msg) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: msg, path: ['password'] })
    }
    if (v.password !== v.confirm) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'Passwords do not match', path: ['confirm'] })
    }
  })

type AccountValues = z.infer<typeof accountSchema>

export function RegisterPage({ onLogin }: { onLogin?: (user: User) => void }) {
  const navigate = useNavigate()
  const [step, setStep] = useState(0)
  const [scrolled, setScrolled] = useState(false)
  const [pisAck, setPisAck] = useState(false)
  const [consents, setConsents] = useState<boolean[]>(Array(18).fill(false))
  const [affirm, setAffirm] = useState(false)
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const {
    register,
    trigger,
    getValues,
    formState: { errors },
  } = useForm<AccountValues>({ resolver: zodResolver(accountSchema) })

  const next = async () => {
    if (step === 0 && !(await trigger())) return
    setStep((s) => s + 1)
  }

  const submit = async () => {
    setError('')
    setSubmitting(true)
    const values = getValues()
    try {
      await api.post('/api/v1/auth/register/complete', {
        username: values.username,
        password: values.password,
        confirm_password: values.confirm,
        pharmacist_registration_id: values.pharmacist_registration_id,
        age_over_18: true,
        pis_version: DOCUMENT_VERSION,
        pis_scroll_acknowledged: true,
        pis_label_accepted: true,
        consent_form_version: DOCUMENT_VERSION,
        accepted_statement_numbers: consentStatements.map((_, i) => i + 1),
        electronic_affirmation: true,
      })
      // Auto-login so the pending pharmacist can view registration status immediately
      try {
        const { data } = await api.post<LoginResponse>('/api/v1/auth/login', {
          username: values.username,
          password: values.password,
        })
        localStorage.setItem('access_token', data.access_token)
        localStorage.setItem('refresh_token', data.refresh_token)
        localStorage.setItem('user', JSON.stringify(data.user))
        onLogin?.(data.user)
      } catch {
        /* registration succeeded; status page still works via state */
      }
      navigate('/registration-status', {
        state: {
          username: values.username,
          justRegistered: true,
        },
      })
    } catch (err: unknown) {
      const detail =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined
      setError(
        typeof detail === 'string'
          ? detail
          : 'Registration could not be completed. Check details or try a different username.',
      )
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Card>
      <CardContent>
        <Typography variant="h4">Pharmacist registration</Typography>
        <Typography color="text.secondary" mb={2}>
          Only pharmacists may self-register. An administrator must approve your account before you can
          use clinical features (Prescription Analyzer).
        </Typography>
        <Stepper activeStep={step} sx={{ mb: 3 }}>
          {['Account', 'PIS', 'Consent', 'Review'].map((label) => (
            <Step key={label}>
              <StepLabel>{label}</StepLabel>
            </Step>
          ))}
        </Stepper>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        {step === 0 && (
          <Stack spacing={2}>
            <TextField
              label="Pharmacist Registration ID"
              error={!!errors.pharmacist_registration_id}
              helperText={errors.pharmacist_registration_id?.message}
              {...register('pharmacist_registration_id')}
            />
            <TextField
              label="Username / User ID"
              error={!!errors.username}
              helperText={errors.username?.message}
              {...register('username')}
            />
            <TextField
              label="Password"
              type="password"
              error={!!errors.password}
              helperText={
                errors.password?.message ||
                '12+ characters; at least 3 of: lower, upper, digit, symbol'
              }
              {...register('password')}
            />
            <TextField
              label="Confirm password"
              type="password"
              error={!!errors.confirm}
              helperText={errors.confirm?.message}
              {...register('confirm')}
            />
            <FormControlLabel
              control={<Checkbox {...register('adult')} />}
              label="I confirm that I am 18 years of age or older."
            />
            {errors.adult && (
              <Typography color="error">You must confirm you are 18 or older.</Typography>
            )}
          </Stack>
        )}

        {step === 1 && (
          <>
            <Typography variant="h6">Participant Information Sheet</Typography>
            <Typography color="text.secondary" mb={1}>
              Version {DOCUMENT_VERSION} · {DOCUMENT_DATE}
            </Typography>
            <Box
              tabIndex={0}
              onScroll={(e) => {
                const el = e.currentTarget
                if (el.scrollTop + el.clientHeight >= el.scrollHeight - 8) setScrolled(true)
              }}
              sx={{
                whiteSpace: 'pre-line',
                height: 320,
                overflow: 'auto',
                border: 1,
                borderColor: 'divider',
                borderRadius: 2,
                p: 2,
                bgcolor: 'grey.50',
              }}
            >
              {pisText}
            </Box>
            <Stack direction="row" spacing={1} mt={2}>
              <Button onClick={() => window.print()}>Print</Button>
              <Button
                component="a"
                href={`data:text/plain;charset=utf-8,${encodeURIComponent(pisText)}`}
                download="pis-v1.0.txt"
              >
                Download
              </Button>
            </Stack>
            <FormControlLabel
              sx={{ mt: 2 }}
              control={
                <Checkbox
                  checked={pisAck}
                  disabled={!scrolled}
                  onChange={(e) => setPisAck(e.target.checked)}
                />
              }
              label={scrolled ? PIS_ACK_LABEL : 'Please scroll to the end before acknowledging.'}
            />
          </>
        )}

        {step === 2 && (
          <>
            <Typography variant="h6">Participant Consent Form</Typography>
            <Typography color="text.secondary" mb={2}>
              Version {DOCUMENT_VERSION} · {DOCUMENT_DATE}. Each statement is mandatory.
            </Typography>
            <List dense>
              {consentStatements.map((text, i) => (
                <ListItem key={text} disablePadding sx={{ mb: 1 }}>
                  <FormControlLabel
                    control={
                      <Checkbox
                        checked={consents[i]}
                        onChange={(e) =>
                          setConsents((all) => all.map((v, n) => (n === i ? e.target.checked : v)))
                        }
                      />
                    }
                    label={`${i + 1}. ${text}`}
                  />
                </ListItem>
              ))}
            </List>
            <FormControlLabel
              control={<Checkbox checked={affirm} onChange={(e) => setAffirm(e.target.checked)} />}
              label={ELECTRONIC_AFFIRMATION}
            />
          </>
        )}

        {step === 3 && (
          <Stack spacing={1}>
            <Typography variant="h6">Review and submit</Typography>
            <Typography>Registration ID: {getValues('pharmacist_registration_id')}</Typography>
            <Typography>Username: {getValues('username')}</Typography>
            <Alert severity="info">
              You will submit PIS and Consent Form version {DOCUMENT_VERSION}. Your account remains
              pending until an administrator approves it. Clinical features stay locked until then.
            </Alert>
          </Stack>
        )}

        <Stack direction="row" spacing={2} mt={3}>
          <Button disabled={step === 0 || submitting} onClick={() => setStep((s) => s - 1)}>
            Back
          </Button>
          {step < 3 ? (
            <Button
              variant="contained"
              onClick={next}
              disabled={
                (step === 1 && (!scrolled || !pisAck)) ||
                (step === 2 && (!affirm || consents.some((c) => !c)))
              }
            >
              Continue
            </Button>
          ) : (
            <Button variant="contained" onClick={() => void submit()} disabled={submitting}>
              {submitting ? 'Submitting…' : 'Submit registration'}
            </Button>
          )}
          <Button component={RouterLink} to="/login" disabled={submitting}>
            Cancel
          </Button>
        </Stack>
      </CardContent>
    </Card>
  )
}
