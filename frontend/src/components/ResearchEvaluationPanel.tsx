import { useCallback, useEffect, useState } from 'react'
import {
  Alert,
  Box,
  Button,
  Chip,
  Divider,
  MenuItem,
  Stack,
  Tab,
  Tabs,
  TextField,
  Typography,
} from '@mui/material'
import { api } from '../api'

type MetricEnv = {
  metric: string
  value: number | null
  availability: string
  note?: string | null
}

function MetricValue({ m }: { m?: MetricEnv | null }) {
  if (!m) return <Typography>—</Typography>
  if (m.availability !== 'AVAILABLE') {
    return (
      <Chip
        size="small"
        label={m.availability}
        color={m.availability === 'NOT_VERIFIABLE' ? 'warning' : 'default'}
      />
    )
  }
  return <Typography variant="body1">{typeof m.value === 'number' ? m.value.toFixed(4) : String(m.value)}</Typography>
}

export function ResearchEvaluationPanel() {
  const [tab, setTab] = useState(0)
  const [status, setStatus] = useState<Record<string, unknown> | null>(null)
  const [cases, setCases] = useState<Array<Record<string, unknown>>>([])
  const [error, setError] = useState('')
  const [caseCode, setCaseCode] = useState('CASE-001')
  const [selectedCaseId, setSelectedCaseId] = useState('')
  const [gtText, setGtText] = useState('')
  const [gtFields, setGtFields] = useState({
    medicine_name: '',
    strength: '',
    dosage_form: '',
    route: '',
    dose: '',
    frequency: '',
    duration: '',
  })
  const [dq1Result, setDq1Result] = useState<Record<string, unknown> | null>(null)
  const [dq2Result, setDq2Result] = useState<Record<string, unknown> | null>(null)
  const [dq3Result, setDq3Result] = useState<Record<string, unknown> | null>(null)
  const [dq4Summary, setDq4Summary] = useState<Record<string, unknown> | null>(null)
  const [busy, setBusy] = useState(false)

  const [importNote, setImportNote] = useState('')

  const refresh = useCallback(() => {
    Promise.all([
      api.get('/api/v1/research/eval/status'),
      api.get('/api/v1/research/eval/cases'),
      api.get('/api/v1/research/eval/dq4/summary'),
    ])
      .then(([s, c, d4]) => {
        setStatus(s.data)
        setCases(c.data)
        setDq4Summary(d4.data)
        if (!selectedCaseId && c.data?.[0]?.id) setSelectedCaseId(String(c.data[0].id))
      })
      .catch(() => setError('Could not load research evaluation status (reviewer role required).'))
  }, [selectedCaseId])

  useEffect(() => {
    refresh()
  }, [refresh])

  useEffect(() => {
    if (!selectedCaseId) return
    api
      .get(`/api/v1/research/eval/cases/${selectedCaseId}/ground-truth`)
      .then(({ data }) => {
        const gt = data.ground_truth
        if (!gt) return
        setGtText(String(gt.instruction_text || ''))
        setGtFields({
          medicine_name: String(gt.medicine_name || ''),
          strength: String(gt.strength || ''),
          dosage_form: String(gt.dosage_form || ''),
          route: String(gt.route || ''),
          dose: String(gt.dose || ''),
          frequency: String(gt.frequency || ''),
          duration: String(gt.duration || ''),
        })
      })
      .catch(() => {
        /* draft may not exist yet */
      })
  }, [selectedCaseId])

  async function importDataset(writeDraftGt: boolean) {
    setBusy(true)
    setImportNote('')
    try {
      const { data } = await api.post('/api/v1/research/eval/import', {
        write_draft_gt: writeDraftGt,
        import_examples: false,
        reviewer_pseudonym: 'REV-01',
      })
      setImportNote(JSON.stringify(data.cases || data, null, 2))
      refresh()
    } catch {
      setError('Dataset import failed. Ensure data/research_evaluation/cases_v1.json exists on the API host.')
    } finally {
      setBusy(false)
    }
  }

  async function createCase() {
    setBusy(true)
    try {
      const { data } = await api.post('/api/v1/research/eval/cases', {
        case_code: caseCode,
        synthetic_prescription_ref: `SYN-${caseCode}`,
        approved_reviewer_pseudonym: 'REV-01',
      })
      setSelectedCaseId(data.id)
      refresh()
    } catch {
      setError('Failed to create evaluation case.')
    } finally {
      setBusy(false)
    }
  }

  async function saveGroundTruth() {
    if (!selectedCaseId) return
    setBusy(true)
    try {
      await api.post('/api/v1/research/eval/ground-truth', {
        evaluation_case_id: selectedCaseId,
        instruction_text: gtText,
        ...gtFields,
        reviewer_pseudonym: 'REV-01',
      })
      refresh()
    } catch {
      setError('Failed to save ground truth.')
    } finally {
      setBusy(false)
    }
  }

  async function runDq1() {
    if (!selectedCaseId) return
    setBusy(true)
    try {
      const { data } = await api.post(`/api/v1/research/eval/dq1/run/${selectedCaseId}`)
      setDq1Result(data)
      refresh()
    } catch {
      setError('DQ1 run failed — ensure ground truth exists.')
    } finally {
      setBusy(false)
    }
  }

  async function seedGoldAndRunDq2() {
    if (!selectedCaseId) return
    setBusy(true)
    try {
      await api.post('/api/v1/research/eval/dq2/gold-standard', {
        evaluation_case_id: selectedCaseId,
        reference_medicine: 'Ibuprofen 200 mg tablet',
        candidate_medicine: 'Ibuprofen 200 mg film-coated tablet',
        candidate_type: 'SAME_ACTIVE_MOIETY_PRODUCT',
        candidate_rank: 1,
        same_active_ingredient: true,
        same_active_moiety: true,
        pharmacist_valid_candidate: true,
        pharmacist_reason: null,
        evidence_source: 'FDA_NDC',
        reviewer_pseudonym: 'PHARM-01',
      })
      await api.post('/api/v1/research/eval/dq2/gold-standard', {
        evaluation_case_id: selectedCaseId,
        reference_medicine: 'Ibuprofen 200 mg tablet',
        candidate_medicine: 'Naproxen 250 mg tablet',
        candidate_type: 'DIFFERENT_ACTIVE_INGREDIENT',
        candidate_rank: 2,
        same_active_ingredient: false,
        same_active_moiety: false,
        pharmacist_valid_candidate: false,
        pharmacist_reason: 'ACTIVE_INGREDIENT_MISMATCH',
        evidence_source: 'DrugBank',
        reviewer_pseudonym: 'PHARM-01',
      })
      const { data } = await api.post('/api/v1/research/eval/dq2/run')
      setDq2Result(data)
      refresh()
    } catch {
      setError('DQ2 run failed.')
    } finally {
      setBusy(false)
    }
  }

  async function runDq3() {
    setBusy(true)
    try {
      const { data } = await api.post('/api/v1/research/eval/dq3/run', {
        evaluation_case_id: selectedCaseId || null,
        query: 'ibuprofen pain inflammation',
      })
      setDq3Result(data)
      refresh()
    } catch {
      setError('DQ3 run failed.')
    } finally {
      setBusy(false)
    }
  }

  async function previewDq4Conditions() {
    setBusy(true)
    try {
      const { data } = await api.post('/api/v1/research/eval/dq4/assign', {
        participant_pseudonym: 'PREVIEW-ONLY',
        evaluation_case_id: selectedCaseId || null,
        candidate_name: 'Ibuprofen 200 mg',
        candidate_type: 'SAME_ACTIVE_MOIETY_PRODUCT',
        provenance: { fda_ndc: '00000-0000', drugbank_id: 'DB01050' },
      })
      setDq4Summary({
        availability: 'NOT_CALCULATED',
        note: 'Condition payloads previewed in-app. Likert collection is external — import responses after export from Forms/other platform.',
        preview_order: data.order,
        preview_assignments: data.assignments,
      })
    } catch {
      setError('Could not preview DQ4 explanation conditions.')
    } finally {
      setBusy(false)
    }
  }

  async function importExternalSurvey() {
    setBusy(true)
    try {
      const { data } = await api.post('/api/v1/research/eval/import', {
        write_draft_gt: false,
        import_examples: false,
        reviewer_pseudonym: 'REV-01',
      })
      const summary = await api.get('/api/v1/research/eval/dq4/summary')
      setDq4Summary(summary.data)
      setImportNote(
        `Survey import: ${JSON.stringify(data.survey || { survey_inserted: 0 })}. Fill survey_responses_v1.json from your external questionnaire export first.`,
      )
      refresh()
    } catch {
      setError('Could not import external questionnaire responses.')
    } finally {
      setBusy(false)
    }
  }

  async function freezeSnapshot() {
    setBusy(true)
    try {
      await api.post('/api/v1/research/eval/snapshots/freeze')
      refresh()
    } catch {
      setError('Snapshot freeze failed.')
    } finally {
      setBusy(false)
    }
  }

  const sampleClaims = (status?.sample_claims || {}) as Record<string, unknown>
  const counts = (status?.counts || {}) as Record<string, number>

  return (
    <Stack spacing={2} sx={{ mt: 3 }}>
      <Divider />
      <Typography variant="h5">Research Evaluation</Typography>
      <Alert severity="info">
        Reviewer-only research layer. Production Analyzer OCR remains Google Vision primary. DQ1 here is a
        multi-engine WER/CER comparison (including Spec-named TrOCR) against pharmacist-confirmed ground
        truth. Unavailable metrics are never shown as zero.
      </Alert>
      {error && (
        <Alert severity="error" onClose={() => setError('')}>
          {error}
        </Alert>
      )}

      <Tabs value={tab} onChange={(_, v) => setTab(v)} variant="scrollable" allowScrollButtonsMobile>
        <Tab label="Dataset & ground truth" />
        <Tab label="DQ1 — OCR" />
        <Tab label="DQ2 — Candidates" />
        <Tab label="DQ3 — RAG" />
        <Tab label="DQ4 — XAI & trust" />
        <Tab label="Combined & export" />
      </Tabs>

      {tab === 0 && (
        <Stack spacing={2}>
          <Alert severity="success">
            Prefer real stored cases over demo buttons. Edit{' '}
            <code>data/research_evaluation/cases_v1.json</code>, import below, then set ground truth to{' '}
            <strong>confirmed</strong> only after pharmacist review.
          </Alert>
          <Typography variant="body2" color="text.secondary">
            Spec sample: 25–30 synthetic prescriptions. Metrics stay unavailable until pharmacist-confirmed
            ground truth exists. Do not invent aggregate scores.
          </Typography>
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1}>
            <Button variant="contained" disabled={busy} onClick={() => void importDataset(false)}>
              Import cases (confirmed GT only)
            </Button>
            <Button variant="outlined" disabled={busy} onClick={() => void importDataset(true)}>
              Import cases + draft GT for confirmation
            </Button>
          </Stack>
          {importNote && (
            <Box component="pre" sx={{ fontSize: 12, bgcolor: 'grey.50', p: 1.5, borderRadius: 1, overflow: 'auto' }}>
              {importNote}
            </Box>
          )}
          <Divider />
          <Typography variant="subtitle2">Manual case / confirm ground truth</Typography>
          <Typography variant="body2" color="text.secondary">
            Pseudonymous evaluation cases only — no patient-identifying information. Saving ground truth here
            marks the case pharmacist-confirmed.
          </Typography>
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1}>
            <TextField
              size="small"
              label="Case code"
              value={caseCode}
              onChange={(e) => setCaseCode(e.target.value)}
            />
            <Button variant="outlined" disabled={busy} onClick={() => void createCase()}>
              Create single case
            </Button>
          </Stack>
          <TextField
            select
            size="small"
            label="Selected case"
            value={selectedCaseId}
            onChange={(e) => setSelectedCaseId(e.target.value)}
            sx={{ maxWidth: 480 }}
          >
            {cases.map((c) => (
              <MenuItem key={String(c.id)} value={String(c.id)}>
                {String(c.case_code)} · {String(c.ground_truth_status)}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            multiline
            minRows={2}
            label="Pharmacist-confirmed instruction (ground truth)"
            value={gtText}
            onChange={(e) => setGtText(e.target.value)}
          />
          <Box sx={{ display: 'grid', gap: 1, gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' } }}>
            {(
              [
                ['medicine_name', 'Medicine'],
                ['strength', 'Strength'],
                ['dosage_form', 'Dosage form'],
                ['route', 'Route'],
                ['dose', 'Dose'],
                ['frequency', 'Frequency'],
                ['duration', 'Duration'],
              ] as const
            ).map(([key, label]) => (
              <TextField
                key={key}
                size="small"
                label={label}
                value={gtFields[key]}
                onChange={(e) => setGtFields((prev) => ({ ...prev, [key]: e.target.value }))}
              />
            ))}
          </Box>
          <Button variant="contained" disabled={busy || !selectedCaseId} onClick={() => void saveGroundTruth()}>
            Confirm ground truth for selected case
          </Button>
          <Typography variant="caption">Cases loaded: {cases.length}</Typography>
        </Stack>
      )}

      {tab === 1 && (
        <Stack spacing={2}>
          <Alert severity="warning">
            <strong>DQ1 — OCR accuracy (reviewer evidence only).</strong> Production Analyzer HITL keeps{' '}
            <strong>Google Vision</strong> as primary. This tab compares engines independently against
            pharmacist-confirmed ground truth. Do not invent WER/CER.
          </Alert>
          <Typography variant="body2">
            <strong>Reframed research question:</strong> How accurately does the PharmaAssist OCR pipeline
            (and each configured engine, including TrOCR) extract medicine names and dosages, measured by
            WER and CER against pharmacist-confirmed ground truth?
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Spec DQ1 named TrOCR specifically — report the TrOCR arm as the Spec-named engine, alongside
            Vision (production primary), hybrid/production path, PaddleOCR (detect assist), and Tesseract
            (Spec fallback).
          </Typography>
          <Box sx={{ display: 'grid', gap: 1, gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' } }}>
            {(
              [
                ['trocr', 'TrOCR', 'Spec-named DQ1 engine'],
                ['google_vision', 'Google Vision', 'Production primary (HITL)'],
                ['hybrid', 'Hybrid / production path', 'What pharmacists use'],
                ['paddleocr', 'PaddleOCR', 'Optional line-detection assist'],
                ['tesseract', 'Tesseract', 'Spec final / local fallback'],
              ] as const
            ).map(([id, label, role]) => (
              <Box key={id} sx={{ p: 1.25, bgcolor: 'grey.50', borderRadius: 1 }}>
                <Typography fontWeight={600}>{label}</Typography>
                <Typography variant="caption" color="text.secondary">
                  {role}
                </Typography>
              </Box>
            ))}
          </Box>
          <Button variant="contained" disabled={busy || !selectedCaseId} onClick={() => void runDq1()}>
            Run multi-engine OCR evaluation (confirmed GT required)
          </Button>
          {dq1Result && (
            <Box>
              <Stack direction="row" flexWrap="wrap" gap={1} sx={{ mb: 1 }}>
                <Chip label={`availability: ${String(dq1Result.availability)}`} />
                {dq1Result.availability === 'INSUFFICIENT_GROUND_TRUTH' && (
                  <Chip color="warning" label="Confirm ground truth first" />
                )}
              </Stack>
              {dq1Result.production_note && (
                <Typography variant="body2" sx={{ mb: 1 }}>
                  {String(dq1Result.production_note)}
                </Typography>
              )}
              <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                {String(dq1Result.normalisation_note || '')}
              </Typography>
              <Typography variant="subtitle2" sx={{ mb: 1 }}>
                Comparative results (per engine — independent outputs)
              </Typography>
              {Object.entries(
                (dq1Result.engines as Record<
                  string,
                  { metrics: Record<string, MetricEnv>; thesis_role?: Record<string, string> }
                >) || {},
              ).map(([engine, payload]) => {
                const role = payload.thesis_role || {}
                return (
                  <Box key={engine} sx={{ mb: 1.5, p: 1.5, bgcolor: 'grey.50', borderRadius: 1 }}>
                    <Stack direction="row" flexWrap="wrap" gap={1} alignItems="center" sx={{ mb: 0.5 }}>
                      <Typography fontWeight={600}>{String(role.label || engine)}</Typography>
                      {role.thesis_role && <Chip size="small" label={String(role.thesis_role)} />}
                    </Stack>
                    {role.operational_role && (
                      <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1 }}>
                        Ops: {String(role.operational_role)}
                      </Typography>
                    )}
                    <Stack direction="row" flexWrap="wrap" gap={2}>
                      <Box>
                        <Typography variant="caption">WER</Typography>
                        <MetricValue m={payload.metrics?.wer} />
                      </Box>
                      <Box>
                        <Typography variant="caption">CER</Typography>
                        <MetricValue m={payload.metrics?.cer} />
                      </Box>
                      <Box>
                        <Typography variant="caption">Name exact</Typography>
                        <MetricValue m={payload.metrics?.medicine_name_exact_match} />
                      </Box>
                      <Box>
                        <Typography variant="caption">Name F1</Typography>
                        <MetricValue m={payload.metrics?.medicine_name_f1} />
                      </Box>
                      <Box>
                        <Typography variant="caption">Latency (ms)</Typography>
                        <MetricValue m={payload.metrics?.processing_time_ms} />
                      </Box>
                    </Stack>
                  </Box>
                )
              })}
              <Typography variant="caption" color="text.secondary">
                Export comparative figures from Combined &amp; export after freezing a snapshot. Do not claim
                TrOCR is better or worse until these values are calculated on confirmed cases.
              </Typography>
            </Box>
          )}
        </Stack>
      )}

      {tab === 2 && (
        <Stack spacing={2}>
          <Alert severity="info">
            DQ2 metrics require pharmacist gold-standard rows in{' '}
            <code>gold_standards_v1.json</code> (or API). The button below is a smoke-test seed only — do not
            treat it as dissertation evidence.
          </Alert>
          <Alert severity="warning">
            Structural similarity is supporting evidence only and does not establish clinical interchangeability.
          </Alert>
          <Button variant="outlined" color="warning" disabled={busy || !selectedCaseId} onClick={() => void seedGoldAndRunDq2()}>
            Smoke-test only: seed example gold &amp; run P@K
          </Button>
          {dq2Result && (
            <Box>
              <Chip label={`availability: ${String(dq2Result.availability)}`} sx={{ mb: 1 }} />
              {(['rules_only', 'rules_plus_mcs'] as const).map((cond) => {
                const block = dq2Result[cond] as Record<string, MetricEnv> | undefined
                if (!block) return null
                return (
                  <Box key={cond} sx={{ mb: 1.5 }}>
                    <Typography fontWeight={600}>{cond}</Typography>
                    <Stack direction="row" gap={2} flexWrap="wrap">
                      <Box>
                        <Typography variant="caption">P@1</Typography>
                        <MetricValue m={block.precision_at_1} />
                      </Box>
                      <Box>
                        <Typography variant="caption">P@3</Typography>
                        <MetricValue m={block.precision_at_3} />
                      </Box>
                      <Box>
                        <Typography variant="caption">R@3</Typography>
                        <MetricValue m={block.recall_at_3} />
                      </Box>
                    </Stack>
                  </Box>
                )
              })}
            </Box>
          )}
        </Stack>
      )}

      {tab === 3 && (
        <Stack spacing={2}>
          <Button variant="contained" disabled={busy} onClick={() => void runDq3()}>
            Run RAG comparison (none / keyword / FAISS)
          </Button>
          {dq3Result &&
            ((dq3Result.conditions as Array<Record<string, unknown>>) || []).map((row) => (
              <Box key={String(row.retrieval_method)} sx={{ p: 1.5, bgcolor: 'grey.50', borderRadius: 1 }}>
                <Typography fontWeight={600}>{String(row.retrieval_method)}</Typography>
                <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', mb: 1 }}>
                  {String(row.explanation || '').slice(0, 400)}
                </Typography>
                <Stack direction="row" gap={2}>
                  <Box>
                    <Typography variant="caption">Citation coverage</Typography>
                    <MetricValue m={(row.metrics as Record<string, MetricEnv>)?.citation_coverage} />
                  </Box>
                  <Box>
                    <Typography variant="caption">Unsupported-claim rate</Typography>
                    <MetricValue m={(row.metrics as Record<string, MetricEnv>)?.unsupported_claim_rate} />
                  </Box>
                  <Box>
                    <Typography variant="caption">BERTScore F1</Typography>
                    <MetricValue m={(row.metrics as Record<string, MetricEnv>)?.bertscore_f1} />
                  </Box>
                </Stack>
              </Box>
            ))}
        </Stack>
      )}

      {tab === 4 && (
        <Stack spacing={2}>
          <Alert severity="info">
            The pharmacist questionnaire is <strong>not collected inside PharmaAssist</strong>. Share it on an
            external platform (e.g. Microsoft Forms v1.2). After export, map responses into{' '}
            <code>data/research_evaluation/survey_responses_v1.json</code> (pseudonyms only — no names, emails,
            registration numbers, workplaces, or IPs), then import below.
          </Alert>
          <Typography variant="body2">
            In-app DQ4 support is limited to explanation Conditions A / B / C for the session design. Trust
            metrics come only from imported external responses.
          </Typography>
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1}>
            <Button variant="outlined" disabled={busy} onClick={() => void previewDq4Conditions()}>
              Preview explanation conditions A/B/C
            </Button>
            <Button variant="contained" disabled={busy} onClick={() => void importExternalSurvey()}>
              Import questionnaire export (JSON)
            </Button>
          </Stack>
          {dq4Summary && (
            <Box>
              <Chip label={`availability: ${String(dq4Summary.availability)}`} sx={{ mb: 1 }} />
              <Typography variant="body2">
                Responses: {String(dq4Summary.response_count ?? '—')} · Pharmacists:{' '}
                {String(dq4Summary.pharmacist_count ?? '—')}
              </Typography>
              <pre style={{ fontSize: 12, overflow: 'auto' }}>
                {JSON.stringify(dq4Summary, null, 2)}
              </pre>
            </Box>
          )}
        </Stack>
      )}

      {tab === 5 && (
        <Stack spacing={2}>
          <Typography variant="h6">Combined results</Typography>
          <Stack direction="row" flexWrap="wrap" gap={1}>
            {Object.entries(counts).map(([k, v]) => (
              <Chip key={k} label={`${k}: ${v}`} />
            ))}
          </Stack>
          <Alert severity="warning">
            {String(sampleClaims.display || 'Sample claims derived from stored records only.')}
          </Alert>
          <Typography variant="body2">
            DQ readiness — DQ1: {String((status?.dq1 as Record<string, string>)?.readiness)} · DQ2:{' '}
            {String((status?.dq2 as Record<string, string>)?.readiness)} · DQ3:{' '}
            {String((status?.dq3 as Record<string, string>)?.readiness)} · DQ4:{' '}
            {String((status?.dq4 as Record<string, string>)?.readiness)}
          </Typography>
          <Stack direction="row" gap={1} flexWrap="wrap">
            <Button variant="contained" disabled={busy} onClick={() => void freezeSnapshot()}>
              Freeze immutable snapshot
            </Button>
            <Button
              variant="outlined"
              component="a"
              href="/api/v1/research/eval/export/csv?kind=status"
              target="_blank"
            >
              Export CSV
            </Button>
            <Button variant="outlined" component="a" href="/api/v1/research/eval/export/json" target="_blank">
              Export JSON
            </Button>
          </Stack>
        </Stack>
      )}
    </Stack>
  )
}
