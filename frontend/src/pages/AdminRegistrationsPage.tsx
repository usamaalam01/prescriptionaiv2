import { useCallback, useEffect, useState } from 'react'
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  Stack,
  Tab,
  Tabs,
  TextField,
  Typography,
} from '@mui/material'
import { api } from '../api'

interface RegistrationItem {
  id: string
  username: string
  requested_role: string
  status: string
  submitted_at?: string
  encrypted_registration_data: boolean
}

type FilterStatus = 'pending_review' | 'approved' | 'rejected'

function formatSubmittedAt(iso?: string) {
  if (!iso) return 'Unknown'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString()
}

export function AdminRegistrationsPage() {
  const [filter, setFilter] = useState<FilterStatus>('pending_review')
  const [items, setItems] = useState<RegistrationItem[]>([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [dialog, setDialog] = useState<{
    id: string
    username: string
    decision: 'approve' | 'reject'
  } | null>(null)
  const [reason, setReason] = useState('')
  const [actionError, setActionError] = useState('')

  const load = useCallback(() => {
    setError('')
    setBusy(true)
    api
      .get<RegistrationItem[]>('/api/v1/admin/registrations', { params: { status: filter } })
      .then(({ data }) => setItems(data))
      .catch(() => setError('Could not load registration requests.'))
      .finally(() => setBusy(false))
  }, [filter])

  useEffect(() => {
    load()
  }, [load])

  const openDecide = (item: RegistrationItem, decision: 'approve' | 'reject') => {
    setActionError('')
    setReason('')
    setDialog({ id: item.id, username: item.username, decision })
  }

  const confirmDecide = async () => {
    if (!dialog) return
    setActionError('')
    try {
      await api.post(`/api/v1/admin/registrations/${dialog.id}/${dialog.decision}`, {
        confirmed_role: 'pharmacist',
        reason: reason.trim() || null,
      })
      setDialog(null)
      load()
    } catch {
      setActionError('Decision could not be saved. Try again.')
    }
  }

  return (
    <Stack spacing={2}>
      <Typography variant="h4">Registration requests</Typography>

      <Tabs
        value={filter}
        onChange={(_e, v: FilterStatus) => setFilter(v)}
        variant="scrollable"
        allowScrollButtonsMobile
      >
        <Tab value="pending_review" label="Pending" />
        <Tab value="approved" label="Approved" />
        <Tab value="rejected" label="Rejected" />
      </Tabs>

      {error && <Alert severity="error">{error}</Alert>}
      {busy && !items.length && !error && (
        <Typography color="text.secondary">Loading…</Typography>
      )}
      {!busy && !items.length && !error && (
        <Alert severity="info">
          No {filter.replaceAll('_', ' ')} registration requests.
        </Alert>
      )}

      {items.map((item) => (
        <Card key={item.id}>
          <CardContent>
            <Stack spacing={0.75}>
              <Typography fontWeight={700}>{item.username}</Typography>
              <Typography variant="body2" color="text.secondary">
                Requested role: {item.requested_role} · Status: {item.status.replaceAll('_', ' ')}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Submitted: {formatSubmittedAt(item.submitted_at)}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Encrypted registration ID on file:{' '}
                {item.encrypted_registration_data ? 'yes' : 'no'}
              </Typography>
            </Stack>
            {filter === 'pending_review' && (
              <Stack direction="row" spacing={1} mt={2}>
                <Button
                  color="success"
                  variant="contained"
                  onClick={() => openDecide(item, 'approve')}
                >
                  Approve
                </Button>
                <Button color="error" variant="outlined" onClick={() => openDecide(item, 'reject')}>
                  Reject
                </Button>
              </Stack>
            )}
          </CardContent>
        </Card>
      ))}

      <Dialog open={Boolean(dialog)} onClose={() => setDialog(null)} fullWidth maxWidth="sm">
        <DialogTitle>
          {dialog?.decision === 'approve' ? 'Approve registration' : 'Reject registration'}
        </DialogTitle>
        <DialogContent>
          <DialogContentText sx={{ mb: 2 }}>
            {dialog?.decision === 'approve'
              ? `Approve ${dialog?.username} as a pharmacist? They will gain access to the Prescription Analyzer.`
              : `Reject ${dialog?.username}? Their account will remain inactive.`}
          </DialogContentText>
          {dialog?.decision === 'reject' && (
            <TextField
              label="Reason (optional)"
              fullWidth
              multiline
              minRows={2}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          )}
          {actionError && (
            <Alert severity="error" sx={{ mt: 2 }}>
              {actionError}
            </Alert>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialog(null)}>Cancel</Button>
          <Button
            color={dialog?.decision === 'approve' ? 'success' : 'error'}
            variant="contained"
            onClick={() => void confirmDecide()}
          >
            Confirm {dialog?.decision}
          </Button>
        </DialogActions>
      </Dialog>

      <Box>
        <Button variant="outlined" onClick={load} disabled={busy}>
          Refresh list
        </Button>
      </Box>
    </Stack>
  )
}
