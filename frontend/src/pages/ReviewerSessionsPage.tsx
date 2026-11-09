import { useEffect, useState } from 'react'
import { Link as RouterLink, useNavigate, useParams } from 'react-router-dom'
import {
  Alert,
  Box,
  Button,
  Chip,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material'
import { api } from '../api'

interface PrescriptionListPayload {
  items: Array<{
    session_id: string
    status: string
    pharmacist_username?: string | null
    original_filename: string
    medicines_total: number
    medicines_confirmed: number
    has_analytics: boolean
    created_at?: string | null
  }>
  disclaimer: string
}

interface SessionDetail {
  id: string
  status: string
  original_filename: string
  content_type: string
  file_size_bytes: number
  selected_ocr_engine: string | null
  temporary_deleted_at: string | null
  pharmacist_username: string | null
  ocr_raw_text: string | null
  ocr_confidence: number | null
  ocr_is_mock: boolean | null
}

interface MedicineRow {
  id: string
  item_number: number
  ai_medicine_name: string
  ai_strength: string | null
  ai_form: string | null
  ai_dose: string | null
  ai_route: string | null
  ai_frequency: string | null
  ai_duration: string | null
  parser_confidence: number
  formulary_matched: boolean
  formulary_warnings: string[]
  pharmacist_status: string
  pharmacist_medicine_name: string | null
  pharmacist_strength: string | null
  pharmacist_form: string | null
  pharmacist_dose: string | null
  pharmacist_route: string | null
  pharmacist_frequency: string | null
  pharmacist_duration: string | null
  pharmacist_reason: string | null
}

export function ReviewerSessionsPage() {
  const [data, setData] = useState<PrescriptionListPayload | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api
      .get<PrescriptionListPayload>('/api/v1/reviewer/prescriptions')
      .then(({ data: d }) => setData(d))
      .catch(() => setError('Could not load prescription sessions.'))
  }, [])

  return (
    <Stack spacing={2}>
      <Stack direction="row" justifyContent="space-between" alignItems="center" flexWrap="wrap" gap={1}>
        <Typography variant="h4">Prescription sessions</Typography>
        <Button component={RouterLink} to="/research/evaluation" variant="outlined" size="small">
          Back to evaluation snapshot
        </Button>
      </Stack>

      {error && <Alert severity="error">{error}</Alert>}
      {data && <Alert severity="info">{data.disclaimer}</Alert>}

      {!data && !error && <Typography color="text.secondary">Loading sessions…</Typography>}

      {data && (
        <TableContainer component={Paper} sx={{ border: 1, borderColor: 'divider' }}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Filename</TableCell>
                <TableCell>Pharmacist</TableCell>
                <TableCell>Status</TableCell>
                <TableCell align="right">Confirmed</TableCell>
                <TableCell>Created</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {data.items.map((row) => (
                <TableRow
                  key={row.session_id}
                  hover
                  component={RouterLink}
                  to={`/research/sessions/${row.session_id}`}
                  sx={{ textDecoration: 'none', cursor: 'pointer' }}
                >
                  <TableCell>{row.original_filename}</TableCell>
                  <TableCell>{row.pharmacist_username || '—'}</TableCell>
                  <TableCell>
                    <Chip size="small" label={row.status} />
                  </TableCell>
                  <TableCell align="right">
                    {row.medicines_confirmed}/{row.medicines_total}
                  </TableCell>
                  <TableCell>{row.created_at ? new Date(row.created_at).toLocaleString() : '—'}</TableCell>
                </TableRow>
              ))}
              {!data.items.length && (
                <TableRow>
                  <TableCell colSpan={5}>
                    <Typography color="text.secondary">No prescription sessions yet.</Typography>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Stack>
  )
}

export function ReviewerSessionDetailPage() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const navigate = useNavigate()
  const [session, setSession] = useState<SessionDetail | null>(null)
  const [medicines, setMedicines] = useState<MedicineRow[] | null>(null)
  const [imageUrl, setImageUrl] = useState<string | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!sessionId) return
    let revoke: string | null = null

    api
      .get<SessionDetail>(`/api/v1/reviewer/prescriptions/${sessionId}`)
      .then(({ data }) => setSession(data))
      .catch(() => setError('Could not load this session.'))

    api
      .get<MedicineRow[]>(`/api/v1/reviewer/prescriptions/${sessionId}/medicines`)
      .then(({ data }) => setMedicines(data))
      .catch(() => setError('Could not load extracted medicines.'))

    api
      .get(`/api/v1/reviewer/prescriptions/${sessionId}/image`, { responseType: 'blob' })
      .then(({ data }) => {
        const url = URL.createObjectURL(data as Blob)
        revoke = url
        setImageUrl(url)
      })
      .catch(() => {
        /* image may be deleted/expired — not an error for the detail view */
      })

    return () => {
      if (revoke) URL.revokeObjectURL(revoke)
    }
  }, [sessionId])

  return (
    <Stack spacing={2}>
      <Stack direction="row" justifyContent="space-between" alignItems="center" flexWrap="wrap" gap={1}>
        <Typography variant="h4">Session detail</Typography>
        <Button variant="outlined" size="small" onClick={() => navigate('/research/sessions')}>
          Back to sessions
        </Button>
      </Stack>

      {error && <Alert severity="error">{error}</Alert>}
      <Alert severity="warning">Read-only review. Reviewers cannot edit pharmacist entries.</Alert>

      {!session && !error && <Typography color="text.secondary">Loading…</Typography>}

      {session && (
        <Paper variant="outlined" sx={{ p: 2 }}>
          <Stack spacing={0.5}>
            <Typography variant="h6">{session.original_filename}</Typography>
            <Typography color="text.secondary">Pharmacist: {session.pharmacist_username || '—'}</Typography>
            <Stack direction="row" spacing={1} alignItems="center">
              <Chip size="small" label={session.status} />
              {session.selected_ocr_engine && (
                <Chip size="small" variant="outlined" label={`OCR: ${session.selected_ocr_engine}`} />
              )}
              {session.ocr_is_mock && <Chip size="small" color="warning" label="mock OCR" />}
            </Stack>
          </Stack>
        </Paper>
      )}

      {imageUrl && (
        <Paper variant="outlined" sx={{ p: 2 }}>
          <Typography variant="subtitle2" color="text.secondary" mb={1}>
            Uploaded prescription image
          </Typography>
          <Box
            component="img"
            src={imageUrl}
            alt="Uploaded prescription"
            sx={{ maxWidth: '100%', maxHeight: 480, borderRadius: 1, border: 1, borderColor: 'divider' }}
          />
        </Paper>
      )}

      {medicines && (
        <TableContainer component={Paper} sx={{ border: 1, borderColor: 'divider' }}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>#</TableCell>
                <TableCell>AI-extracted</TableCell>
                <TableCell>Pharmacist-verified</TableCell>
                <TableCell>Status</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {medicines.map((m) => (
                <TableRow key={m.id}>
                  <TableCell>{m.item_number}</TableCell>
                  <TableCell>
                    <Typography variant="body2" fontWeight={600}>
                      {m.ai_medicine_name}
                    </Typography>
                    <Typography variant="caption" color="text.secondary" display="block">
                      {[m.ai_strength, m.ai_form, m.ai_route, m.ai_dose, m.ai_frequency, m.ai_duration]
                        .filter(Boolean)
                        .join(' · ') || '—'}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    {m.pharmacist_status === 'confirmed' || m.pharmacist_medicine_name ? (
                      <>
                        <Typography variant="body2" fontWeight={600}>
                          {m.pharmacist_medicine_name || m.ai_medicine_name}
                        </Typography>
                        <Typography variant="caption" color="text.secondary" display="block">
                          {[
                            m.pharmacist_strength,
                            m.pharmacist_form,
                            m.pharmacist_route,
                            m.pharmacist_dose,
                            m.pharmacist_frequency,
                            m.pharmacist_duration,
                          ]
                            .filter(Boolean)
                            .join(' · ') || '—'}
                        </Typography>
                        {m.pharmacist_reason && (
                          <Typography variant="caption" color="text.secondary" display="block">
                            Reason: {m.pharmacist_reason}
                          </Typography>
                        )}
                      </>
                    ) : (
                      <Typography color="text.secondary">Not yet reviewed</Typography>
                    )}
                  </TableCell>
                  <TableCell>
                    <Chip size="small" label={m.pharmacist_status} />
                  </TableCell>
                </TableRow>
              ))}
              {!medicines.length && (
                <TableRow>
                  <TableCell colSpan={4}>
                    <Typography color="text.secondary">No medicines extracted for this session.</Typography>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Stack>
  )
}
