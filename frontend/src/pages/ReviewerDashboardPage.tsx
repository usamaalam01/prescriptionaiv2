import { useEffect, useState } from 'react'
import {
  Alert,
  Box,
  Button,
  Chip,
  Link,
  Stack,
  Typography,
} from '@mui/material'
import { api } from '../api'
import { ResearchEvaluationPanel } from '../components/ResearchEvaluationPanel'

interface Snapshot {
  phase: string
  disclaimer: string
  sessions_total: number
  ocr_jobs_total: number
  medicines_extracted_total: number
  formulary_matched_total: number
  formulary_match_rate: number | null
  verification_by_status: Record<string, number>
  pharmacist_reviewed_total: number
  override_or_correction_rate: number | null
  avg_ocr_confidence: number | null
  avg_parser_confidence: number | null
  alternative_suggestions_total: number
  alternative_feedback_by_decision: Record<string, number>
  knowledge_mode: string
}

function pct(value: number | null): string {
  if (value === null || value === undefined) return '—'
  return `${(value * 100).toFixed(1)}%`
}

export function ReviewerDashboardPage({ onLogout }: { onLogout?: () => void }) {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api
      .get<Snapshot>('/api/v1/research/evaluation-snapshot')
      .then(({ data }) => setSnapshot(data))
      .catch(() => setError('Could not load evaluation snapshot.'))
  }, [])

  if (error) return <Alert severity="error">{error}</Alert>
  if (!snapshot) return <Typography>Loading evaluation metrics…</Typography>

  return (
    <Stack spacing={2}>
      <Stack direction="row" justifyContent="space-between" alignItems="center" flexWrap="wrap" gap={1}>
        <Typography variant="h4">Research evaluation snapshot</Typography>
        {onLogout && (
          <Button variant="outlined" size="small" onClick={() => void onLogout()}>
            Logout
          </Button>
        )}
      </Stack>
      <Alert severity="warning">{snapshot.disclaimer}</Alert>
      <Alert severity="info">
        For dissertation DQ1, use <strong>Research Evaluation → DQ1 — OCR</strong> below: multi-engine WER/CER
        vs pharmacist ground truth (TrOCR Spec-named; Google Vision remains production primary).
      </Alert>
      <Typography variant="body2" color="text.secondary">
        Phase {snapshot.phase} · Knowledge mode: {snapshot.knowledge_mode} · Aggregate metrics only (no patient
        identifiers).
      </Typography>

      <Box sx={{ display: 'grid', gap: 1.5, gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' } }}>
        <Metric label="Review sessions" value={String(snapshot.sessions_total)} />
        <Metric label="OCR / pipeline jobs" value={String(snapshot.ocr_jobs_total)} />
        <Metric label="Medicines extracted" value={String(snapshot.medicines_extracted_total)} />
        <Metric label="Formulary matched" value={`${snapshot.formulary_matched_total} (${pct(snapshot.formulary_match_rate)})`} />
        <Metric label="Pharmacist reviewed" value={String(snapshot.pharmacist_reviewed_total)} />
        <Metric label="Correction rate" value={pct(snapshot.override_or_correction_rate)} />
        <Metric label="Avg OCR confidence" value={pct(snapshot.avg_ocr_confidence)} />
        <Metric label="Avg parser confidence" value={pct(snapshot.avg_parser_confidence)} />
        <Metric label="Alternative suggestions" value={String(snapshot.alternative_suggestions_total)} />
      </Box>

      <Typography variant="h6">Verification by status</Typography>
      <Stack direction="row" flexWrap="wrap" gap={1}>
        {Object.entries(snapshot.verification_by_status).map(([status, count]) => (
          <Chip key={status} label={`${status}: ${count}`} />
        ))}
        {Object.keys(snapshot.verification_by_status).length === 0 && (
          <Typography color="text.secondary">No verification events yet.</Typography>
        )}
      </Stack>

      <Typography variant="h6">Alternative feedback</Typography>
      <Stack direction="row" flexWrap="wrap" gap={1}>
        {Object.entries(snapshot.alternative_feedback_by_decision).map(([decision, count]) => (
          <Chip key={decision} color="secondary" label={`${decision}: ${count}`} />
        ))}
        {Object.keys(snapshot.alternative_feedback_by_decision).length === 0 && (
          <Typography color="text.secondary">No alternative feedback yet.</Typography>
        )}
      </Stack>

      <Typography variant="caption" color="text.secondary">
        Evidence sources used in this prototype are synthetic DrugBank/FDA-style seed records. See{' '}
        <Link href="https://go.drugbank.com/" target="_blank" rel="noreferrer">
          DrugBank
        </Link>{' '}
        /{' '}
        <Link href="https://www.accessdata.fda.gov/" target="_blank" rel="noreferrer">
          FDA
        </Link>{' '}
        for the intended future live adapters.
      </Typography>

      <ResearchEvaluationPanel />
    </Stack>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <Box sx={{ bgcolor: 'grey.50', borderRadius: 2, p: 2 }}>
      <Typography variant="caption" color="text.secondary">
        {label}
      </Typography>
      <Typography variant="h6">{value}</Typography>
    </Box>
  )
}
