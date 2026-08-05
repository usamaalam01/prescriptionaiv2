import { useCallback, useEffect, useState } from 'react'
import {
  Alert,
  Box,
  Chip,
  LinearProgress,
  Stack,
  Tab,
  Tabs,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material'
import { useSearchParams } from 'react-router-dom'
import { Button } from '@mui/material'
import { api } from '../api'
import { AdminRegistrationsPage } from './AdminRegistrationsPage'

type AdminTab = 'dashboard' | 'registrations' | 'catalog' | 'prescriptions' | 'analytics'

interface DashboardPayload {
  disclaimer: string
  pharmacists: {
    total: number
    active: number
    pending: number
    list?: Array<{
      username: string
      status: string
      is_active: boolean
      registration_status: string
      submitted_at?: string | null
    }>
  }
  registrations: {
    pending_review: number
    approved: number
    rejected: number
    excluded_test_accounts?: number
  }
  data_policy?: {
    excluded_registration_accounts?: number
    excluded_sessions?: Record<string, number>
  }
  prescriptions: {
    sessions_total: number
    reviewed_with_confirmations: number
    submitted: number
    in_progress_estimate: number
    medicines_confirmed: number
  }
  catalog: {
    available: boolean
    built_at?: string | null
    medicines?: number | null
    products?: number | null
    sources: Array<{ id: string; label: string; role: string; rows_ingested?: number | null }>
  }
}

interface CatalogPayload {
  available: boolean
  built_at?: string | null
  disclaimer?: string
  sources: Array<{ id: string; label: string; role: string; rows_ingested?: number | null }>
  unified?: Record<string, number | string | null | undefined>
}

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

interface AnalyticsPayload {
  disclaimer: string
  prescriptions_evaluated: number
  data_policy?: {
    skipped?: Record<string, number>
  }
  averages: {
    cer: number | null
    wer: number | null
    entity_precision: number | null
    entity_recall: number | null
    entity_f1: number | null
    bertscore_precision: number | null
    bertscore_recall: number | null
    bertscore_f1: number | null
  }
  prescriptions: Array<{
    session_id: string
    status: string
    pharmacist_username?: string | null
    cer: number | null
    wer: number | null
    entity_f1: number | null
    bertscore_f1: number | null
    medicines_confirmed?: number | null
  }>
}

function Kpi({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <Box
      sx={{
        p: 1.5,
        borderRadius: 2,
        border: '1px solid',
        borderColor: 'divider',
        bgcolor: '#FAFBFC',
        minWidth: 0,
      }}
    >
      <Typography variant="caption" color="text.secondary" display="block" noWrap title={label}>
        {label}
      </Typography>
      <Typography variant="h5" fontWeight={700} sx={{ mt: 0.5 }}>
        {value}
      </Typography>
      {hint && (
        <Typography variant="caption" color="text.secondary">
          {hint}
        </Typography>
      )}
    </Box>
  )
}

function fmt(v: number | null | undefined, kind: 'int' | 'pct' | 'rate' = 'int') {
  if (v == null) return '—'
  if (kind === 'int') return String(v)
  if (kind === 'pct') return `${Number(v).toFixed(2)}%`
  return Number(v).toFixed(4)
}

function DashboardTab() {
  const [data, setData] = useState<DashboardPayload | null>(null)
  const [error, setError] = useState('')

  const load = useCallback(() => {
    setError('')
    api
      .get<DashboardPayload>('/api/v1/admin/dashboard')
      .then(({ data: d }) => setData(d))
      .catch(() => setError('Could not load admin dashboard.'))
  }, [])

  useEffect(() => {
    load()
  }, [load])

  if (error) return <Alert severity="error">{error}</Alert>
  if (!data) return <Typography color="text.secondary">Loading dashboard…</Typography>

  return (
    <Stack spacing={2}>
      <Box
        sx={{
          display: 'grid',
          gap: 1.25,
          gridTemplateColumns: { xs: 'repeat(2, 1fr)', md: 'repeat(4, 1fr)' },
        }}
      >
        <Kpi
          label="Pharmacists registered"
          value={fmt(data.pharmacists.total)}
          hint={`${data.pharmacists.active} active · ${data.pharmacists.pending} pending`}
        />
        <Kpi label="Pending registrations" value={fmt(data.registrations.pending_review)} />
        <Kpi label="Prescriptions submitted" value={fmt(data.prescriptions.submitted)} />
        <Kpi
          label="Prescriptions reviewed"
          value={fmt(data.prescriptions.reviewed_with_confirmations)}
          hint={`${data.prescriptions.medicines_confirmed} medicines confirmed`}
        />
      </Box>
      <Box
        sx={{
          display: 'grid',
          gap: 1.25,
          gridTemplateColumns: { xs: 'repeat(2, 1fr)', md: 'repeat(4, 1fr)' },
        }}
      >
        <Kpi label="Approved registrations" value={fmt(data.registrations.approved)} />
        <Kpi label="Rejected registrations" value={fmt(data.registrations.rejected)} />
        <Kpi label="Sessions total" value={fmt(data.prescriptions.sessions_total)} />
        <Kpi
          label="Catalog medicines"
          value={data.catalog.available ? fmt(data.catalog.medicines) : 'Unavailable'}
          hint={data.catalog.available ? 'FDA NDC + DrugBank + SPL' : undefined}
        />
      </Box>

      <Typography variant="subtitle1" fontWeight={700}>
        Registered pharmacists
      </Typography>
      {(data.pharmacists.list || []).length === 0 ? (
        <Alert severity="info">No self-registered pharmacists yet.</Alert>
      ) : (
        <TableContainer sx={{ border: 1, borderColor: 'divider', borderRadius: 2 }}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Username</TableCell>
                <TableCell>Account</TableCell>
                <TableCell>Registration</TableCell>
                <TableCell>Submitted</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {(data.pharmacists.list || []).map((p) => (
                <TableRow key={p.username}>
                  <TableCell sx={{ fontWeight: 700 }}>{p.username}</TableCell>
                  <TableCell>
                    <Chip size="small" label={p.status} color={p.status === 'active' ? 'success' : 'default'} />
                  </TableCell>
                  <TableCell>{p.registration_status.replaceAll('_', ' ')}</TableCell>
                  <TableCell>
                    {p.submitted_at ? new Date(p.submitted_at).toLocaleString() : '—'}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      <Stack direction="row" spacing={1}>
        <Button size="small" variant="outlined" onClick={load}>
          Refresh
        </Button>
      </Stack>
    </Stack>
  )
}

function CatalogTab() {
  const [data, setData] = useState<CatalogPayload | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api
      .get<CatalogPayload>('/api/v1/admin/catalog')
      .then(({ data: d }) => setData(d))
      .catch(() => setError('Could not load catalog information.'))
  }, [])

  if (error) return <Alert severity="error">{error}</Alert>
  if (!data) return <Typography color="text.secondary">Loading catalog…</Typography>

  return (
    <Stack spacing={2}>
      <Alert severity={data.available ? 'success' : 'warning'}>
        Catalog {data.available ? 'available' : 'not built'}
        {data.built_at ? ` · built ${data.built_at}` : ''}
      </Alert>
      <Box sx={{ display: 'grid', gap: 1.25, gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' } }}>
        <Kpi label="Unified medicines" value={fmt(data.unified?.medicines as number)} />
        <Kpi label="Products" value={fmt(data.unified?.products as number)} />
        <Kpi label="Aliases" value={fmt(data.unified?.aliases as number)} />
        <Kpi label="Label sections" value={fmt(data.unified?.label_sections as number)} />
      </Box>
      <Typography variant="subtitle1" fontWeight={700}>
        Sources
      </Typography>
      <Stack spacing={1}>
        {(data.sources || []).map((s) => (
          <Box key={s.id} sx={{ p: 1.5, border: 1, borderColor: 'divider', borderRadius: 2 }}>
            <Typography fontWeight={700}>
              {s.label}{' '}
              <Chip size="small" label={s.id} sx={{ ml: 1 }} />
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {s.role}
            </Typography>
            <Typography variant="body2">Rows ingested: {fmt(s.rows_ingested)}</Typography>
          </Box>
        ))}
      </Stack>
    </Stack>
  )
}

function PrescriptionsTab() {
  const [data, setData] = useState<PrescriptionListPayload | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api
      .get<PrescriptionListPayload>('/api/v1/admin/prescriptions')
      .then(({ data: d }) => setData(d))
      .catch(() => setError('Could not load prescriptions.'))
  }, [])

  if (error) return <Alert severity="error">{error}</Alert>
  if (!data) return <Typography color="text.secondary">Loading prescriptions…</Typography>

  return (
    <Stack spacing={2}>
      <Alert severity="info">
        PharmaAssist is a pharmacist decision-support prototype using curated datasets. It is not a
        clinical care system and must not be used as the sole basis for prescribing, dispensing, or
        patient treatment decisions.
      </Alert>
      {!data.items.length && (
        <Typography color="text.secondary">No prescription sessions yet.</Typography>
      )}
      <TableContainer sx={{ border: 1, borderColor: 'divider', borderRadius: 2 }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Filename</TableCell>
              <TableCell>Pharmacist</TableCell>
              <TableCell>Status</TableCell>
              <TableCell align="right">Confirmed</TableCell>
              <TableCell>Created</TableCell>
              <TableCell>Analytics</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {data.items.map((row) => (
              <TableRow key={row.session_id}>
                <TableCell>{row.original_filename}</TableCell>
                <TableCell>{row.pharmacist_username || '—'}</TableCell>
                <TableCell>
                  <Chip size="small" label={row.status} />
                </TableCell>
                <TableCell align="right">
                  {row.medicines_confirmed}/{row.medicines_total}
                </TableCell>
                <TableCell>
                  {row.created_at ? new Date(row.created_at).toLocaleString() : '—'}
                </TableCell>
                <TableCell>{row.has_analytics ? 'Yes' : '—'}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Stack>
  )
}

function AnalyticsTab() {
  const [data, setData] = useState<AnalyticsPayload | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    setBusy(true)
    setError('')
    api
      .get<AnalyticsPayload>('/api/v1/admin/analytics/prescriptions')
      .then(({ data: d }) => setData(d))
      .catch(() => setError('Could not load prescription analytics.'))
      .finally(() => setBusy(false))
  }, [])

  useEffect(() => {
    load()
  }, [load])

  if (error) return <Alert severity="error">{error}</Alert>
  if (!data) {
    return (
      <Stack spacing={1}>
        <Typography color="text.secondary">Loading prescription-level analytics…</Typography>
        {busy && <LinearProgress />}
      </Stack>
    )
  }

  const a = data.averages
  return (
    <Stack spacing={2}>
      <Alert severity="info">Prescription-level metrics using curated datasets.</Alert>
      <Box
        sx={{
          display: 'grid',
          gap: 1.25,
          gridTemplateColumns: { xs: 'repeat(2, 1fr)', md: 'repeat(4, 1fr)' },
        }}
      >
        <Kpi label="Avg CER (lower better)" value={fmt(a.cer, 'pct')} />
        <Kpi label="Avg WER (lower better)" value={fmt(a.wer, 'pct')} />
        <Kpi label="Avg entity F1" value={fmt(a.entity_f1, 'rate')} />
        <Kpi label="Avg BertScore F1" value={fmt(a.bertscore_f1, 'rate')} />
      </Box>
      <Box
        sx={{
          display: 'grid',
          gap: 1.25,
          gridTemplateColumns: { xs: 'repeat(2, 1fr)', md: 'repeat(3, 1fr)' },
        }}
      >
        <Kpi label="Avg entity Precision" value={fmt(a.entity_precision, 'rate')} />
        <Kpi label="Avg entity Recall" value={fmt(a.entity_recall, 'rate')} />
        <Kpi label="Avg BertScore Precision" value={fmt(a.bertscore_precision, 'rate')} />
      </Box>

      <Typography variant="subtitle1" fontWeight={700}>
        Per prescription
      </Typography>
      <TableContainer sx={{ border: 1, borderColor: 'divider', borderRadius: 2 }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Pharmacist</TableCell>
              <TableCell>Session</TableCell>
              <TableCell>Status</TableCell>
              <TableCell align="right">CER %</TableCell>
              <TableCell align="right">WER %</TableCell>
              <TableCell align="right">Entity F1</TableCell>
              <TableCell align="right">BertScore F1</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {data.prescriptions.map((row) => (
              <TableRow key={row.session_id}>
                <TableCell sx={{ fontWeight: 700 }}>{row.pharmacist_username || '—'}</TableCell>
                <TableCell sx={{ fontFamily: 'ui-monospace, Consolas, monospace', fontSize: 12 }}>
                  {row.session_id.slice(0, 8)}…
                </TableCell>
                <TableCell>{row.status}</TableCell>
                <TableCell align="right">{fmt(row.cer, 'pct')}</TableCell>
                <TableCell align="right">{fmt(row.wer, 'pct')}</TableCell>
                <TableCell align="right">{fmt(row.entity_f1, 'rate')}</TableCell>
                <TableCell align="right">{fmt(row.bertscore_f1, 'rate')}</TableCell>
              </TableRow>
            ))}
            {!data.prescriptions.length && (
              <TableRow>
                <TableCell colSpan={7}>
                  <Typography color="text.secondary">No evaluated prescriptions yet.</Typography>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>
      <Button size="small" variant="outlined" onClick={load} disabled={busy}>
        {busy ? 'Refreshing…' : 'Refresh analytics'}
      </Button>
    </Stack>
  )
}

export function AdminPortalPage({ onLogout }: { onLogout?: () => void }) {
  const [params, setParams] = useSearchParams()
  const tab = (params.get('tab') as AdminTab) || 'dashboard'
  const setTab = (next: AdminTab) => {
    setParams(next === 'dashboard' ? {} : { tab: next })
  }

  return (
    <Stack spacing={2}>
      <Stack direction="row" justifyContent="space-between" alignItems="center" flexWrap="wrap" gap={1}>
        <Typography variant="h4">Administrator portal</Typography>
        {onLogout && (
          <Button variant="outlined" size="small" onClick={() => void onLogout()}>
            Logout
          </Button>
        )}
      </Stack>
      <Tabs
        value={tab}
        onChange={(_e, v: AdminTab) => setTab(v)}
        variant="scrollable"
        allowScrollButtonsMobile
      >
        <Tab value="dashboard" label="Dashboard" />
        <Tab value="registrations" label="Registrations" />
        <Tab value="catalog" label="Catalog" />
        <Tab value="prescriptions" label="Prescriptions" />
        <Tab value="analytics" label="Analytics" />
      </Tabs>

      {tab === 'dashboard' && <DashboardTab />}
      {tab === 'registrations' && <AdminRegistrationsPage />}
      {tab === 'catalog' && <CatalogTab />}
      {tab === 'prescriptions' && <PrescriptionsTab />}
      {tab === 'analytics' && <AnalyticsTab />}
    </Stack>
  )
}
