import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Alert,
  Box,
  Button,
  Chip,
  LinearProgress,
  Stack,
  Tab,
  Tabs,
  Typography,
} from '@mui/material'
import { Link as RouterLink, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import { VerificationTable, type VerificationRow } from '../components/VerificationTable'
import { TherapeuticAlternativesPanel } from '../components/TherapeuticAlternativesPanel'
import { SummaryAnalyticsPanel } from '../components/SummaryAnalyticsPanel'
import { OcrConflictPanel } from '../components/OcrConflictPanel'

interface SessionInfo {
  id: string
  status: string
  original_filename: string
  file_size_bytes: number
}

interface OcrResult {
  id: string
  engine: string
  raw_text: string
  confidence: number
  is_mock: boolean
  status?: string
  processing_ms?: number
  warnings?: string[]
  pipeline?: {
    merged_lines?: Array<{
      line_id?: string
      selected_text?: string
      selected_engine?: string
      selected_confidence?: number
      conflict?: boolean
      used_trocr_retry?: boolean
      candidates?: Array<{ text?: string; engine?: string; confidence?: number }>
    }>
    warnings?: string[]
  } | null
}

interface CatalogOverview {
  available: boolean
  disclaimer?: string
  intended_use?: string
  built_at?: string
  sources?: Array<{ id: string; label: string; role: string; rows_ingested?: number | null }>
  retention?: {
    retention_hours?: number
    delete_when_session_confirmed?: boolean
    note?: string
  }
  unified?: {
    medicines?: number
    aliases?: number
    full_data?: boolean
  }
}

type WorkspaceTab = 'hitl' | 'alternatives' | 'analytics'

const STEPS = ['Upload', 'OCR pipeline', 'HITL verify', 'Confirm & review'] as const

function formatBytes(n: number) {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / (1024 * 1024)).toFixed(1)} MB`
}

export function AnalyzerPage({ onLogout }: { onLogout?: () => void }) {
  const [searchParams] = useSearchParams()
  const [file, setFile] = useState<File | null>(null)
  const [session, setSession] = useState<SessionInfo | null>(null)
  const [ocr, setOcr] = useState<OcrResult | null>(null)
  const [verificationRows, setVerificationRows] = useState<VerificationRow[]>([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [imageUrl, setImageUrl] = useState<string | null>(null)
  const [uploadOk, setUploadOk] = useState('')
  const [analyticsTick, setAnalyticsTick] = useState(0)
  const [catalog, setCatalog] = useState<CatalogOverview | null>(null)
  const [pipelinePhase, setPipelinePhase] = useState<string>('')
  const [dragOver, setDragOver] = useState(false)
  const [workspaceTab, setWorkspaceTab] = useState<WorkspaceTab>('hitl')
  const hitlRef = useRef<HTMLDivElement | null>(null)
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const resumedSessionRef = useRef<string | null>(null)

  const previewUrl = useMemo(() => (file ? URL.createObjectURL(file) : null), [file])

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl)
      if (imageUrl) URL.revokeObjectURL(imageUrl)
    }
  }, [previewUrl, imageUrl])

  useEffect(() => {
    void api
      .get<CatalogOverview>('/api/v1/catalog/overview')
      .then((res) => setCatalog(res.data))
      .catch(() => setCatalog({ available: false }))
  }, [])

  const confirmedCount = verificationRows.filter((r) => r.pharmacist_status === 'confirmed').length
  const totalRows = verificationRows.length
  const hasHitl = totalRows > 0

  const activeStep = useMemo(() => {
    if (hasHitl && confirmedCount === totalRows && totalRows > 0) return 3
    if (hasHitl) return 2
    if (ocr && (ocr.status === 'completed' || ocr.raw_text)) return 2
    if (session || busy) return 1
    return 0
  }, [hasHitl, confirmedCount, totalRows, ocr, session, busy])

  const loadVerification = async (sessionId: string) => {
    const { data } = await api.get<{ rows: VerificationRow[] }>(
      `/api/v1/reviews/${sessionId}/verification-table`,
    )
    setVerificationRows(data.rows || [])
  }

  // Resume an existing session (e.g. /analyzer?session=<id>) after showcase/script create.
  useEffect(() => {
    const sid = searchParams.get('session')?.trim()
    if (!sid || resumedSessionRef.current === sid) return
    resumedSessionRef.current = sid
    let cancelled = false
    ;(async () => {
      setBusy(true)
      setError('')
      try {
        const { data: sess } = await api.get<SessionInfo>(`/api/v1/prescriptions/${sid}`)
        if (cancelled) return
        setSession(sess)
        setUploadOk('Resumed existing prescription session.')
        setPipelinePhase('completed')
        try {
          const image = await api.get(`/api/v1/prescriptions/${sid}/image`, { responseType: 'blob' })
          if (!cancelled) setImageUrl(URL.createObjectURL(image.data))
        } catch {
          /* image optional */
        }
        try {
          const { data: ocrJob } = await api.get<OcrResult | null>(`/api/v1/ocr/${sid}/results`)
          if (!cancelled && ocrJob) setOcr(ocrJob)
        } catch {
          /* ocr optional */
        }
        await loadVerification(sid)
        setAnalyticsTick((t) => t + 1)
      } catch {
        if (!cancelled) setError('Could not open that prescription session. Check you are signed in as the owner.')
      } finally {
        if (!cancelled) setBusy(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [searchParams])

  const acceptFile = useCallback((next: File | null) => {
    if (!next) return
    const ok =
      next.type === 'image/png' ||
      next.type === 'image/jpeg' ||
      /\.(png|jpe?g)$/i.test(next.name)
    if (!ok) {
      setError('Use a JPG or PNG prescription image. PDF is disabled until page rasterization is available.')
      return
    }
    setError('')
    setFile(next)
    setUploadOk('')
  }, [])

  const upload = async (): Promise<SessionInfo | null> => {
    if (!file) return null
    setBusy(true)
    setError('')
    setUploadOk('')
    setOcr(null)
    setVerificationRows([])
    setPipelinePhase('')
    try {
      const form = new FormData()
      form.append('file', file)
      const { data } = await api.post<SessionInfo>('/api/v1/prescriptions/upload', form)
      setSession(data)
      setUploadOk('Encrypted upload ready.')
      try {
        const image = await api.get(`/api/v1/prescriptions/${data.id}/image`, {
          responseType: 'blob',
        })
        setImageUrl(URL.createObjectURL(image.data))
      } catch {
        /* ignore */
      }
      return data
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        'Upload failed. Use JPG or PNG.'
      setError(typeof detail === 'string' ? detail : 'Upload failed.')
      setSession(null)
      return null
    } finally {
      setBusy(false)
    }
  }

  const sleep = (ms: number) => new Promise((r) => window.setTimeout(r, ms))

  const runPipeline = async () => {
    setError('')
    let active = session
    if (!active) {
      active = await upload()
      if (!active) return
    }
    setBusy(true)
    setPipelinePhase('queued')
    setWorkspaceTab('hitl')
    try {
      const { data: queued } = await api.post<OcrResult>(`/api/v1/ocr/${active.id}/run-async`, {
        engine: 'pipeline',
      })
      let job = queued
      setOcr(job)
      setPipelinePhase(job.status || 'queued')

      const started = Date.now()
      while (job.status === 'queued' || job.status === 'running') {
        if (Date.now() - started > 180_000) {
          throw new Error('OCR job timed out after 3 minutes')
        }
        await sleep(900)
        const { data: next } = await api.get<OcrResult>(`/api/v1/ocr/jobs/${job.id}`)
        job = next
        setOcr(job)
        setPipelinePhase(job.status || 'running')
      }

      if (job.status === 'failed') {
        const warn = (job.warnings || []).join(' ')
        setError(warn || 'OCR pipeline failed.')
        return
      }

      setPipelinePhase('completed')
      await loadVerification(active.id)
      window.setTimeout(() => {
        hitlRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }, 120)
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number; data?: { detail?: string } } })
        ?.response?.status
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      if (status === 401) {
        setError('Session expired. Log out and sign in again, then retry.')
      } else if (err instanceof Error && err.message.includes('timed out')) {
        setError(err.message)
      } else {
        setError(typeof detail === 'string' ? detail : 'Pipeline failed.')
      }
    } finally {
      setBusy(false)
    }
  }

  const cancel = async () => {
    if (!session) return
    setBusy(true)
    try {
      await api.post(`/api/v1/prescriptions/${session.id}/cancel`)
    } finally {
      setSession(null)
      setOcr(null)
      setVerificationRows([])
      setImageUrl(null)
      setFile(null)
      setUploadOk('')
      setPipelinePhase('')
      setWorkspaceTab('hitl')
      setBusy(false)
    }
  }

  const confirmedMedicines = verificationRows
    .filter((r) => r.pharmacist_status === 'confirmed')
    .map((r) => ({
      id: r.medicine_id,
      item_number: r.item_number,
      name: r.fields.drug.value || r.canonical_drug || '',
      strength: r.fields.strength.value,
      form: null,
      route: r.fields.route?.value || null,
      verified_indication: r.fields.indication?.value || null,
    }))

  const catalogStats =
    catalog?.unified?.medicines != null
      ? `${catalog.unified.medicines.toLocaleString()} medicines`
      : null

  const ocrBusy = busy && (pipelinePhase === 'queued' || pipelinePhase === 'running')
  const displayImage = imageUrl || previewUrl

  return (
    <Stack spacing={2.5} sx={{ width: '100%', maxWidth: '100%', overflowX: 'hidden' }}>
      {/* Header */}
      <Stack
        direction={{ xs: 'column', md: 'row' }}
        justifyContent="space-between"
        alignItems={{ md: 'flex-start' }}
        spacing={1.5}
      >
        <Box>
          <Typography
            variant="overline"
            sx={{ letterSpacing: '0.14em', color: 'text.secondary', display: 'block' }}
          >
            Pharmacist workspace
          </Typography>
          <Typography variant="h4" sx={{ fontFamily: '"Source Serif 4", Georgia, serif' }}>
            Prescription Analyzer
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, maxWidth: 560 }}>
            Upload a prescription, run OCR against the FDA NDC / DrugBank / SPL catalog, then confirm
            each field in the HITL table.
          </Typography>
        </Box>
        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
          {catalog && (
            <Chip
              size="small"
              color={catalog.available ? 'success' : 'warning'}
              label={catalog.available ? `Catalog · ${catalogStats || 'ready'}` : 'Catalog missing'}
            />
          )}
          <Button component={RouterLink} to="/catalog" variant="outlined" size="small">
            Browse catalog
          </Button>
          {onLogout && (
            <Button variant="outlined" size="small" onClick={() => void onLogout()}>
              Logout
            </Button>
          )}
        </Stack>
      </Stack>

      {/* Journey steps */}
      <Box
        sx={{
          border: 1,
          borderColor: 'divider',
          borderRadius: 2,
          px: { xs: 1.5, md: 2 },
          py: 1.5,
          bgcolor: 'background.paper',
        }}
      >
        <Stack direction="row" spacing={0} alignItems="center" sx={{ overflowX: 'auto' }}>
          {STEPS.map((label, idx) => {
            const done = idx < activeStep
            const current = idx === activeStep
            return (
              <Stack
                key={label}
                direction="row"
                alignItems="center"
                spacing={1}
                sx={{ flex: '1 1 auto', minWidth: 0 }}
              >
                <Stack direction="row" spacing={1} alignItems="center" sx={{ minWidth: 0 }}>
                  <Box
                    sx={{
                      width: 28,
                      height: 28,
                      borderRadius: '50%',
                      display: 'grid',
                      placeItems: 'center',
                      flexShrink: 0,
                      fontSize: 13,
                      fontWeight: 700,
                      bgcolor: done || current ? 'primary.main' : 'grey.200',
                      color: done || current ? 'primary.contrastText' : 'text.secondary',
                    }}
                  >
                    {done ? '✓' : idx + 1}
                  </Box>
                  <Typography
                    variant="body2"
                    noWrap
                    sx={{
                      fontWeight: current ? 700 : 500,
                      color: current || done ? 'text.primary' : 'text.secondary',
                    }}
                  >
                    {label}
                  </Typography>
                </Stack>
                {idx < STEPS.length - 1 && (
                  <Box
                    sx={{
                      flex: 1,
                      height: 2,
                      mx: 1,
                      minWidth: 12,
                      bgcolor: done ? 'primary.main' : 'grey.200',
                    }}
                  />
                )}
              </Stack>
            )
          })}
        </Stack>
      </Box>

      <Alert severity="warning" sx={{ py: 0.75 }}>
        {catalog?.intended_use ||
          'Decision-support only. Pharmacist confirmation is mandatory. Alternatives are never auto-applied.'}
      </Alert>

      {/* Compact catalog strip */}
      {catalog?.available && (
        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap alignItems="center">
          {(catalog.sources || []).map((s) => (
            <Chip
              key={s.id}
              size="small"
              variant="outlined"
              label={
                s.rows_ingested != null ? `${s.id} · ${s.rows_ingested.toLocaleString()}` : s.id
              }
            />
          ))}
          {catalog.retention?.retention_hours != null && (
            <Typography variant="caption" color="text.secondary">
              Encrypted Rx · {catalog.retention.retention_hours}h retention
              {catalog.retention.delete_when_session_confirmed ? ' · wipe on full confirm' : ''}
            </Typography>
          )}
        </Stack>
      )}

      {/* Upload + run */}
      <Box
        sx={{
          border: 1,
          borderColor: 'divider',
          borderRadius: 2,
          p: { xs: 2, md: 2.5 },
          bgcolor: 'background.paper',
        }}
      >
        <Typography variant="h6" sx={{ mb: 1.5, fontFamily: '"Source Serif 4", Georgia, serif' }}>
          1. Prescription image
        </Typography>

        <Box
          onDragEnter={(e) => {
            e.preventDefault()
            setDragOver(true)
          }}
          onDragOver={(e) => {
            e.preventDefault()
            setDragOver(true)
          }}
          onDragLeave={(e) => {
            e.preventDefault()
            setDragOver(false)
          }}
          onDrop={(e) => {
            e.preventDefault()
            setDragOver(false)
            const dropped = e.dataTransfer.files?.[0]
            if (dropped) acceptFile(dropped)
          }}
          onClick={() => fileInputRef.current?.click()}
          sx={{
            border: '2px dashed',
            borderColor: dragOver ? 'primary.main' : file ? 'success.light' : 'divider',
            bgcolor: dragOver ? 'action.hover' : file ? '#E8F5E9' : 'grey.50',
            borderRadius: 2,
            px: 2,
            py: 3,
            textAlign: 'center',
            cursor: busy ? 'wait' : 'pointer',
            transition: 'border-color 120ms ease, background-color 120ms ease',
          }}
        >
          <input
            ref={fileInputRef}
            hidden
            type="file"
            accept="image/png,image/jpeg"
            onChange={(e) => acceptFile(e.target.files?.[0] || null)}
          />
          <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
            {file ? file.name : 'Drop prescription here, or click to choose'}
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            {file
              ? `${formatBytes(file.size)} · JPG / PNG`
              : 'Accepted: JPG, PNG · PDF disabled until rasterization · encrypted temporary storage'}
          </Typography>
        </Box>

        {session && (
          <Stack
            direction={{ xs: 'column', sm: 'row' }}
            spacing={1}
            alignItems={{ sm: 'center' }}
            sx={{ mt: 1.5 }}
            flexWrap="wrap"
            useFlexGap
          >
            <Chip size="small" color="success" label="Session active" />
            <Typography variant="caption" color="text.secondary">
              {session.original_filename} · {formatBytes(session.file_size_bytes)} ·{' '}
              {session.id.slice(0, 8)}…
            </Typography>
            {pipelinePhase && (
              <Chip
                size="small"
                color={
                  pipelinePhase === 'failed'
                    ? 'error'
                    : pipelinePhase === 'completed'
                      ? 'success'
                      : 'warning'
                }
                label={`OCR: ${pipelinePhase}`}
              />
            )}
            {ocr && ocr.status === 'completed' && (
              <Chip
                size="small"
                variant="outlined"
                color={ocr.is_mock ? 'warning' : 'default'}
                label={
                  ocr.is_mock
                    ? `MOCK OCR · ${(ocr.confidence * 100).toFixed(0)}%`
                    : `Vision · ${(ocr.confidence * 100).toFixed(0)}%`
                }
              />
            )}
            {ocr?.pipeline?.merged_lines && ocr.pipeline.merged_lines.length > 0 && (
              <Chip
                size="small"
                variant="outlined"
                color={
                  ocr.pipeline.merged_lines.some((l) => l.conflict || (l.selected_confidence ?? 1) < 0.78)
                    ? 'warning'
                    : 'success'
                }
                label={`${ocr.pipeline.merged_lines.length} OCR lines · ${
                  ocr.pipeline.merged_lines.filter(
                    (l) => l.conflict || (l.selected_confidence ?? 1) < 0.78,
                  ).length
                } attention`}
              />
            )}
          </Stack>
        )}

        {ocrBusy && (
          <Box sx={{ mt: 1.5 }}>
            <LinearProgress />
            <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
              OCR job {pipelinePhase}
              {ocr?.processing_ms ? ` · last tick ${ocr.processing_ms} ms` : ''} — HITL unlocks when
              complete
            </Typography>
          </Box>
        )}

        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} sx={{ mt: 2 }} useFlexGap>
          <Button
            variant="contained"
            size="large"
            disabled={(!file && !session) || busy}
            onClick={() => void runPipeline()}
            sx={{ minWidth: 200 }}
          >
            {busy
              ? `Working… (${pipelinePhase || 'upload'})`
              : session
                ? 'Run OCR pipeline'
                : 'Upload & run pipeline'}
          </Button>
          <Button
            variant="outlined"
            disabled={!file || busy || Boolean(session)}
            onClick={() => void upload()}
          >
            Upload only
          </Button>
          <Button color="warning" variant="outlined" disabled={!session || busy} onClick={() => void cancel()}>
            Cancel & delete image
          </Button>
        </Stack>

        {uploadOk && !busy && (
          <Alert severity="success" sx={{ mt: 1.5 }}>
            {uploadOk} Use Run OCR pipeline to extract medicines.
          </Alert>
        )}
      </Box>

      {error && (
        <Alert severity="error" onClose={() => setError('')}>
          {error}
        </Alert>
      )}

      {/* Image + OCR text */}
      {(displayImage || ocr) && (
        <Box
          sx={{
            display: 'grid',
            width: '100%',
            gap: 2,
            gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' },
          }}
        >
          <Box
            sx={{
              bgcolor: 'background.paper',
              border: 1,
              borderColor: 'divider',
              borderRadius: 2,
              p: 2,
              minWidth: 0,
            }}
          >
            <Typography variant="subtitle1" fontWeight={700} gutterBottom>
              Prescription image
            </Typography>
            {displayImage ? (
              <Box
                component="img"
                src={displayImage}
                alt="Prescription"
                sx={{
                  width: '100%',
                  maxHeight: 440,
                  objectFit: 'contain',
                  bgcolor: 'grey.100',
                  borderRadius: 1.5,
                }}
              />
            ) : (
              <Typography color="text.secondary">No image preview.</Typography>
            )}
          </Box>

          <Box
            sx={{
              bgcolor: 'background.paper',
              border: 1,
              borderColor: 'divider',
              borderRadius: 2,
              p: 2,
              minWidth: 0,
              display: 'flex',
              flexDirection: 'column',
            }}
          >
            <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1 }}>
              <Typography variant="subtitle1" fontWeight={700}>
                Extracted text
              </Typography>
              {ocr && (
                <Chip
                  size="small"
                  label={`${ocr.engine}${ocr.processing_ms ? ` · ${ocr.processing_ms} ms` : ''}`}
                />
              )}
            </Stack>
            {ocr ? (
              <Stack spacing={1.25} sx={{ flex: 1, minHeight: 0 }}>
                <OcrConflictPanel
                  pipeline={ocr.pipeline}
                  overallConfidence={ocr.confidence}
                  isMock={ocr.is_mock}
                />
                <Box
                  component="pre"
                  sx={{
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                    bgcolor: 'grey.50',
                    border: 1,
                    borderColor: 'divider',
                    p: 1.5,
                    borderRadius: 1.5,
                    maxHeight: 220,
                    overflow: 'auto',
                    m: 0,
                    flex: 1,
                    fontSize: 13,
                    lineHeight: 1.45,
                  }}
                >
                  {ocr.raw_text || '(empty — waiting for OCR text)'}
                </Box>
              </Stack>
            ) : (
              <Typography color="text.secondary">Run the pipeline to populate OCR text.</Typography>
            )}
          </Box>
        </Box>
      )}

      {/* HITL workspace */}
      {session && (
        <Box
          ref={hitlRef}
          sx={{
            bgcolor: 'background.paper',
            border: 1,
            borderColor: hasHitl ? 'primary.light' : 'divider',
            borderRadius: 2,
            overflow: 'hidden',
            width: '100%',
          }}
        >
          <Box
            sx={{
              px: 2,
              pt: 2,
              pb: 0,
              borderBottom: 1,
              borderColor: 'divider',
              bgcolor: '#F8FAFC',
            }}
          >
            <Stack
              direction={{ xs: 'column', sm: 'row' }}
              justifyContent="space-between"
              alignItems={{ sm: 'center' }}
              spacing={1}
              sx={{ mb: 1 }}
            >
              <Box>
                <Typography variant="h6" sx={{ fontFamily: '"Source Serif 4", Georgia, serif' }}>
                  2. Pharmacist verification
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Confirm drug → strength → dose → frequency. Indication is optional for Confirm;
                  required before therapeutic alternatives.
                </Typography>
              </Box>
              {hasHitl && (
                <Stack direction="row" spacing={1} alignItems="center">
                  <Chip
                    size="small"
                    color={confirmedCount === totalRows ? 'success' : 'default'}
                    label={`${confirmedCount} / ${totalRows} confirmed`}
                  />
                  {totalRows > 0 && (
                    <Box sx={{ width: 100 }}>
                      <LinearProgress
                        variant="determinate"
                        value={(confirmedCount / totalRows) * 100}
                        color={confirmedCount === totalRows ? 'success' : 'primary'}
                      />
                    </Box>
                  )}
                </Stack>
              )}
            </Stack>

            <Tabs
              value={workspaceTab}
              onChange={(_e, v: WorkspaceTab) => setWorkspaceTab(v)}
              variant="scrollable"
              scrollButtons="auto"
            >
              <Tab value="hitl" label={`HITL table${hasHitl ? ` (${totalRows})` : ''}`} />
              <Tab
                value="alternatives"
                label={`Alternatives${confirmedCount ? ` (${confirmedCount})` : ''}`}
              />
              <Tab value="analytics" label="Analytics" />
            </Tabs>
          </Box>

          <Box sx={{ p: 2, width: '100%', maxWidth: '100%', overflowX: 'hidden' }}>
            {workspaceTab === 'hitl' && (
              <>
                {!hasHitl && (
                  <Alert severity="info">
                    No medicine rows yet. Upload a prescription and run the OCR pipeline to populate
                    the HITL table.
                  </Alert>
                )}
                {hasHitl && (
                  <VerificationTable
                    sessionId={session.id}
                    rows={verificationRows}
                    onUpdated={(rows) => {
                      setVerificationRows(rows)
                    }}
                  />
                )}
              </>
            )}

            {workspaceTab === 'alternatives' && (
              <TherapeuticAlternativesPanel
                sessionId={session.id}
                confirmedMedicines={confirmedMedicines}
                onDecisionChange={() => setAnalyticsTick((n) => n + 1)}
              />
            )}

            {workspaceTab === 'analytics' && (
              <SummaryAnalyticsPanel
                sessionId={session.id}
                refreshToken={`${confirmedMedicines
                  .map((m) => `${m.id}:${m.verified_indication || ''}`)
                  .join('|')}|${verificationRows.length}|${analyticsTick}`}
              />
            )}
          </Box>
        </Box>
      )}
    </Stack>
  )
}
