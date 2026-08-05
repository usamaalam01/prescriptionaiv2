import { useEffect, useState } from 'react'
import { Alert, Box, Chip, Stack, Typography } from '@mui/material'
import { api } from '../api'

interface HitlEvent {
  id: string
  event_type: string
  field_name?: string | null
  medicine_id?: string | null
  created_at?: string | null
  payload?: {
    previous?: string | null
    new_value?: string | null
    item_number?: number
    drug?: string
    reason?: string
    status?: string
  }
}

export function HitlAuditPanel({
  sessionId,
  refreshToken,
}: {
  sessionId: string
  refreshToken: string
}) {
  const [events, setEvents] = useState<HitlEvent[]>([])
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    void api
      .get<{ events: HitlEvent[] }>(`/api/v1/reviews/${sessionId}/hitl-audit`, {
        params: { limit: 40 },
      })
      .then((res) => {
        if (!cancelled) {
          setEvents(res.data.events || [])
          setError('')
        }
      })
      .catch(() => {
        if (!cancelled) {
          setError('HITL audit trail unavailable (run alembic upgrade if this is a fresh DB).')
          setEvents([])
        }
      })
    return () => {
      cancelled = true
    }
  }, [sessionId, refreshToken])

  return (
    <Stack spacing={1.5}>
      <Typography variant="h6">HITL audit trail</Typography>
      <Typography variant="body2" color="text.secondary">
        Append-only pharmacist field corrections and confirmations for this session (research /
        accountability).
      </Typography>
      {error && <Alert severity="warning">{error}</Alert>}
      {!error && events.length === 0 && (
        <Typography variant="body2" color="text.secondary">
          No HITL edits yet — correct a field or confirm a row to populate this trail.
        </Typography>
      )}
      <Stack spacing={1}>
        {events.map((ev) => {
          const label =
            ev.event_type === 'hitl.row_confirmed'
              ? 'Row confirmed'
              : ev.event_type === 'hitl.row_unidentified'
                ? 'Marked unreadable'
                : ev.event_type === 'hitl.row_excluded'
                  ? 'Excluded'
                  : `Field · ${ev.field_name || '—'}`
          const detail =
            ev.event_type === 'hitl.row_confirmed'
              ? [
                  ev.payload?.drug,
                  ev.payload?.item_number != null ? `#${ev.payload.item_number}` : null,
                ]
                  .filter(Boolean)
                  .join(' · ')
              : ev.event_type?.startsWith('hitl.row_')
                ? `${ev.payload?.drug || '—'} · ${ev.payload?.reason || ''}`
                : `${ev.payload?.previous ?? '∅'} → ${ev.payload?.new_value ?? '∅'}`
          return (
            <Box
              key={ev.id}
              sx={{
                border: 1,
                borderColor: 'divider',
                borderRadius: 1.5,
                px: 1.5,
                py: 1,
                display: 'flex',
                flexWrap: 'wrap',
                gap: 1,
                alignItems: 'center',
              }}
            >
              <Chip
                size="small"
                color={ev.event_type === 'hitl.row_confirmed' ? 'success' : 'default'}
                label={label}
              />
              <Typography variant="body2" sx={{ flex: 1, minWidth: 160 }}>
                {detail}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {ev.created_at ? new Date(ev.created_at).toLocaleString() : ''}
              </Typography>
            </Box>
          )
        })}
      </Stack>
    </Stack>
  )
}
