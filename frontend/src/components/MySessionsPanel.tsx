import { useEffect, useState } from 'react'
import { Alert, Box, Button, Chip, CircularProgress, Stack, Typography } from '@mui/material'
import { Link as RouterLink } from 'react-router-dom'
import { api } from '../api'

interface IncompleteSession {
  id: string
  status: string
  original_filename: string
  created_at?: string | null
}

const STATUS_LABELS: Record<string, string> = {
  ocr_queued: 'OCR running',
  ocr_completed: 'OCR done',
  awaiting_pharmacist_verification: 'Needs verification',
}

export function MySessionsPanel({ refreshToken }: { refreshToken: number }) {
  const [sessions, setSessions] = useState<IncompleteSession[]>([])
  const [error, setError] = useState('')
  const [cancellingId, setCancellingId] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    void api
      .get<IncompleteSession[]>('/api/v1/prescriptions/mine/incomplete')
      .then((res) => {
        if (!cancelled) {
          setSessions(res.data || [])
          setError('')
        }
      })
      .catch(() => {
        if (!cancelled) setError('Could not load your in-progress sessions.')
      })
    return () => {
      cancelled = true
    }
  }, [refreshToken])

  const cancelSession = async (id: string) => {
    if (!window.confirm('Cancel and delete this unfinished prescription session? This cannot be undone.')) {
      return
    }
    setCancellingId(id)
    try {
      await api.post(`/api/v1/prescriptions/${id}/cancel`)
      setSessions((prev) => prev.filter((s) => s.id !== id))
    } catch {
      setError('Could not cancel that session. Please try again.')
    } finally {
      setCancellingId(null)
    }
  }

  if (error) return <Alert severity="error">{error}</Alert>
  if (sessions.length === 0) return null

  return (
    <Box
      sx={{
        bgcolor: '#fff8e1',
        border: 1,
        borderColor: 'warning.light',
        borderRadius: 2,
        p: 2,
      }}
    >
      <Stack spacing={1}>
        <Typography variant="subtitle1" fontWeight={700}>
          Unfinished prescription sessions
        </Typography>
        <Typography variant="body2" color="text.secondary">
          These were uploaded but never confirmed or submitted. Resume one to pick up where you
          left off.
        </Typography>
        <Stack spacing={1}>
          {sessions.map((s) => (
            <Stack
              key={s.id}
              direction={{ xs: 'column', sm: 'row' }}
              spacing={1}
              alignItems={{ sm: 'center' }}
              justifyContent="space-between"
              sx={{ bgcolor: 'background.paper', border: 1, borderColor: 'divider', borderRadius: 1.5, p: 1.25 }}
            >
              <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
                <Typography variant="body2" fontWeight={600}>
                  {s.original_filename}
                </Typography>
                <Chip size="small" label={STATUS_LABELS[s.status] || s.status} />
                {s.created_at && (
                  <Typography variant="caption" color="text.secondary">
                    {new Date(s.created_at).toLocaleString()}
                  </Typography>
                )}
              </Stack>
              <Stack direction="row" spacing={1}>
                <Button
                  component={RouterLink}
                  to={`/analyzer?session=${s.id}`}
                  variant="outlined"
                  size="small"
                >
                  Resume
                </Button>
                <Button
                  color="warning"
                  variant="outlined"
                  size="small"
                  disabled={cancellingId === s.id}
                  onClick={() => void cancelSession(s.id)}
                  startIcon={cancellingId === s.id ? <CircularProgress size={14} /> : undefined}
                >
                  Cancel
                </Button>
              </Stack>
            </Stack>
          ))}
        </Stack>
      </Stack>
    </Box>
  )
}
