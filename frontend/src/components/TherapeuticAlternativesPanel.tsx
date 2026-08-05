import { useMemo, useState } from 'react'
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  Box,
  Button,
  Chip,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import { api } from '../api'

function formatApiDetail(detail: unknown): string {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((d) =>
        typeof d === 'object' && d && 'msg' in d ? String((d as { msg: string }).msg) : JSON.stringify(d),
      )
      .join(' · ')
  }
  if (detail && typeof detail === 'object') return JSON.stringify(detail)
  return 'Request failed.'
}

function statusHelp(status: string, missing: string[]): string | null {
  if (status === 'insufficient_clinical_context') {
    return (
      missing.join(' · ') ||
      'Need a HITL verified indication (and valid allergy status) before alternatives can be ranked.'
    )
  }
  if (status === 'identity_not_confirmed') {
    return (
      missing.join(' · ') ||
      'Medicine identity could not be confirmed in the connected FDA NDC + DrugBank catalog. ' +
        'Confirm the drug name in HITL first, then evaluate again.'
    )
  }
  return null
}

function ProvenanceChip({ label }: { label?: string | null }) {
  const text = (label || '').trim() || 'FDA NDC + DrugBank catalog'
  const isDemo = text === 'DEMO DATA' || text.toUpperCase().includes('DEMO')
  return (
    <Chip
      size="small"
      color={isDemo ? 'warning' : 'success'}
      variant={isDemo ? 'filled' : 'outlined'}
      label={text}
    />
  )
}

interface ConfirmedMedicine {
  id: string
  item_number: number
  name: string
  strength?: string | null
  form?: string | null
  route?: string | null
  verified_indication?: string | null
}

interface Candidate {
  candidate_drug_id: string
  candidate_name: string
  active_ingredient: string
  classification: string
  candidate_type?: string
  display_label?: string
  warning_banner?: string
  status: string
  rank: number | null
  evidence_match_score: number
  evidence_coverage: { coverage_percentage: number; available_domains: number; required_domains: number }
  why_retrieved: string[]
  indication_relationship: { source_condition?: string; candidate_indications?: string[] }
  class_relationship: { source_class?: string; candidate_class?: string }
  mechanism_relationship: { related?: boolean }
  important_differences: string[]
  safety_findings: Array<{ severity?: string; code?: string; message?: string }>
  missing_information: string[]
  warnings?: string[]
  evidence_message?: string | null
  evidence_sufficiency?: string
  passed_filters?: Array<{ code?: string; message?: string }>
  failed_filters?: Array<{ code?: string; message?: string }>
  source_claims: Array<{
    claim_id: string
    claim: string
    source_dataset: string
    source_record_id: string
    source_field_or_section: string
    raw_evidence: string
    demo_label?: string
  }>
  explanation?: { why_ranked?: string; disclaimer?: string; title?: string; primary_explanation_type?: string }
  rule_based_explanation?: {
    title?: string
    final_score?: number
    why_ranked?: string
    experimental_attribution?: { label?: string }
  }
  demo_label?: string
  provenance_label?: string
  mcs?: {
    status?: string
    atom_coverage?: number | null
    mcs_similarity?: number | null
    calculation_status?: string
    limitations?: string
    meets_spec_threshold_0_9?: boolean | null
    note?: string
  }
  feature_attribution?: {
    method?: string
    top_positive?: Array<{ feature?: string; contribution?: number }>
    disclaimer?: string
  }
  rag_evidence?: {
    status?: string
    excerpts?: Array<{ section_key?: string; source?: string; excerpt?: string; score?: number }>
    disclaimer?: string
    evidence_message?: string
  }
}

interface MedicineResult {
  prescription_item_id: string
  source_medicine: {
    medicine_name: string
    ocr_value?: string | null
    pharmacist_confirmed_value?: string | null
    normalisation_suggestion?: {
      input_value?: string | null
      canonical_value?: string | null
      match_method?: string
      confidence?: number
      ui_label?: string
    } | null
  }
  evaluation_status: string
  missing_information: string[]
  product_candidates?: Candidate[]
  therapeutic_candidates?: Candidate[]
  eligible_alternatives: Candidate[]
  blocked_candidates: Candidate[]
  withdrawn_candidates: Candidate[]
  rejected_same_moiety_candidates?: Candidate[]
}

interface EvaluationResponse {
  evaluation_id: string
  disclaimer: string
  demo_label: string
  medicine_results: MedicineResult[]
}

interface MedicineEvalState {
  evaluationId: string
  demoLabel?: string
  result: MedicineResult
}

function CandidateCard({
  prescriptionItemId,
  evaluationId,
  cand,
  decisionReason,
  decisionStatus,
  decisionBusy,
  onReason,
  onDecide,
}: {
  prescriptionItemId: string
  evaluationId: string
  cand: Candidate
  decisionReason: string
  decisionStatus?: 'accept_for_review' | 'reject' | 'request_more_evidence' | null
  decisionBusy?: boolean
  onReason: (v: string) => void
  onDecide: (action: 'accept_for_review' | 'reject' | 'request_more_evidence') => void
}) {
  const decided =
    decisionStatus === 'accept_for_review' ||
    decisionStatus === 'reject' ||
    decisionStatus === 'request_more_evidence'
  const isDifferent = cand.candidate_type === 'DIFFERENT_ACTIVE_INGREDIENT'
  const isProduct = cand.candidate_type === 'SAME_ACTIVE_MOIETY_PRODUCT'
  return (
    <Box sx={{ bgcolor: 'grey.50', borderRadius: 2, p: 1.5 }}>
      {isDifferent && (
        <Alert severity="warning" sx={{ mb: 1 }}>
          {cand.warning_banner || 'Different active ingredient — pharmacist assessment required'}
        </Alert>
      )}
      {cand.evidence_message && (
        <Alert severity="info" sx={{ mb: 1 }}>
          {cand.evidence_message}
        </Alert>
      )}
      <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap mb={1}>
        <Typography fontWeight={700}>
          {cand.rank}. {cand.candidate_name}
        </Typography>
        <Chip
          size="small"
          color={isProduct ? 'primary' : 'warning'}
          label={
            cand.display_label ||
            (isProduct
              ? 'Same-active-moiety product candidate'
              : 'Different-active-ingredient therapeutic candidate')
          }
        />
        <Chip size="small" label={`Rule-based score ${cand.evidence_match_score}/100`} />
        <Chip size="small" label={`Coverage ${cand.evidence_coverage?.coverage_percentage ?? 0}%`} />
        {cand.mcs?.calculation_status === 'ok' && cand.mcs.atom_coverage != null && (
          <Chip size="small" variant="outlined" label={`MCS ${(cand.mcs.atom_coverage * 100).toFixed(0)}%`} />
        )}
        <Chip size="small" label={cand.status} />
        <ProvenanceChip label={cand.provenance_label || cand.demo_label} />
        {decisionStatus === 'accept_for_review' && <Chip size="small" color="success" label="Accepted for review" />}
        {decisionStatus === 'reject' && <Chip size="small" color="error" label="Rejected" />}
        {decisionStatus === 'request_more_evidence' && (
          <Chip size="small" color="info" label="More evidence requested" />
        )}
      </Stack>
      <Typography variant="body2" color="text.secondary" mb={0.5}>
        Candidate alternative for pharmacist review — not an approved substitution.
      </Typography>
      <Typography variant="body2">
        <strong>Why identified:</strong> {(cand.why_retrieved || []).join('; ') || '—'}
      </Typography>
      {(cand.passed_filters || []).length > 0 && (
        <Typography variant="body2">
          <strong>Mandatory filters passed:</strong>{' '}
          {(cand.passed_filters || []).map((f) => f.code).join(', ')}
        </Typography>
      )}
      {(cand.failed_filters || []).length > 0 && (
        <Typography variant="body2" color="error">
          <strong>Mandatory filters failed:</strong>{' '}
          {(cand.failed_filters || []).map((f) => f.message || f.code).join('; ')}
        </Typography>
      )}
      <Typography variant="body2">
        <strong>Indication:</strong> {cand.indication_relationship?.source_condition || '—'} ↔{' '}
        {(cand.indication_relationship?.candidate_indications || []).join(', ') || '—'}
      </Typography>
      <Typography variant="body2">
        <strong>Important differences:</strong> {(cand.important_differences || []).join(' ') || '—'}
      </Typography>
      <Typography variant="body2">
        <strong>Safety findings:</strong>{' '}
        {(cand.safety_findings || []).map((f) => f.message).join('; ') || 'None recorded'}
      </Typography>
      {cand.mcs?.limitations && (
        <Typography variant="caption" color="text.secondary" display="block" mb={1}>
          {cand.mcs.limitations}
        </Typography>
      )}
      <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap mb={1}>
        {[...new Set((cand.source_claims || []).map((c) => c.source_dataset))].map((src) => (
          <Chip key={src} size="small" variant="outlined" label={src} />
        ))}
      </Stack>

      <Accordion disableGutters sx={{ bgcolor: 'transparent', boxShadow: 'none', '&:before': { display: 'none' } }}>
        <AccordionSummary>
          <Typography variant="body2">Evidence provenance</Typography>
        </AccordionSummary>
        <AccordionDetails>
          <Stack spacing={1}>
            {(cand.source_claims || []).map((claim) => (
              <Box key={claim.claim_id} sx={{ border: 1, borderColor: 'divider', borderRadius: 1, p: 1 }}>
                <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap mb={0.5}>
                  <ProvenanceChip label={claim.demo_label} />
                  <Chip size="small" variant="outlined" label={claim.source_dataset} />
                </Stack>
                <Typography variant="caption" display="block">
                  Record: {claim.source_record_id} · Field/section: {claim.source_field_or_section}
                </Typography>
                <Typography variant="body2">{claim.claim}</Typography>
                <Typography variant="caption" color="text.secondary" display="block">
                  Raw evidence: {claim.raw_evidence}
                </Typography>
              </Box>
            ))}
          </Stack>
        </AccordionDetails>
      </Accordion>

      <Accordion disableGutters sx={{ bgcolor: 'transparent', boxShadow: 'none', '&:before': { display: 'none' } }}>
        <AccordionSummary>
          <Typography variant="body2">Rule-based score explanation</Typography>
        </AccordionSummary>
        <AccordionDetails>
          <Stack spacing={1}>
            <Typography variant="body2">
              {cand.rule_based_explanation?.why_ranked || cand.explanation?.why_ranked || '—'}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              Primary explanation is rule-based. Experimental attribution is not definitive.
            </Typography>
            {(cand.feature_attribution?.top_positive || []).length > 0 && (
              <Typography variant="caption" display="block">
                Experimental component contribution:{' '}
                {(cand.feature_attribution?.top_positive || [])
                  .map((f) => `${f.feature} (+${f.contribution})`)
                  .join(', ')}
              </Typography>
            )}
            {(cand.rag_evidence?.excerpts || []).length > 0 ? (
              (cand.rag_evidence?.excerpts || []).map((ex, i) => (
                <Box key={`${ex.section_key}-${i}`} sx={{ border: 1, borderColor: 'divider', borderRadius: 1, p: 1 }}>
                  <Typography variant="caption" display="block">
                    {ex.source} · {ex.section_key}
                  </Typography>
                  <Typography variant="body2">{ex.excerpt}</Typography>
                </Box>
              ))
            ) : (
              <Typography variant="body2">
                {cand.evidence_message ||
                  cand.rag_evidence?.evidence_message ||
                  'Insufficient evidence — pharmacist review required.'}
              </Typography>
            )}
          </Stack>
        </AccordionDetails>
      </Accordion>

      <TextField
        size="small"
        label="Pharmacist reason / professional comment"
        value={decisionReason}
        onChange={(e) => onReason(e.target.value)}
        fullWidth
        multiline
        minRows={2}
        disabled={decided || decisionBusy}
        sx={{ mt: 1, mb: 1 }}
        helperText="Required for Reject or Request more evidence."
      />
      <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
        <Button
          size="small"
          variant="contained"
          color="success"
          disabled={decided || decisionBusy}
          onClick={() => onDecide('accept_for_review')}
        >
          Accept for review
        </Button>
        <Button
          size="small"
          variant="outlined"
          color="error"
          disabled={decided || decisionBusy || !decisionReason.trim()}
          onClick={() => onDecide('reject')}
        >
          Reject
        </Button>
        <Button
          size="small"
          variant="outlined"
          color="info"
          disabled={decided || decisionBusy || !decisionReason.trim()}
          onClick={() => onDecide('request_more_evidence')}
        >
          Request more evidence
        </Button>
      </Stack>
      {/* keep prescriptionItemId/evaluationId referenced for future deep links */}
      <Typography variant="caption" sx={{ display: 'none' }}>
        {prescriptionItemId}:{evaluationId}
      </Typography>
    </Box>
  )
}

export function TherapeuticAlternativesPanel({
  sessionId,
  confirmedMedicines,
  onDecisionChange,
}: {
  sessionId: string
  confirmedMedicines: ConfirmedMedicine[]
  onDecisionChange?: () => void
}) {
  const [allergyStatus, setAllergyStatus] = useState('none_known')
  const [allergies, setAllergies] = useState('')
  const [busyId, setBusyId] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [evalsByMedicine, setEvalsByMedicine] = useState<Record<string, MedicineEvalState>>({})
  const [decisionReason, setDecisionReason] = useState<Record<string, string>>({})
  const [decisionStatus, setDecisionStatus] = useState<
    Record<string, 'accept_for_review' | 'reject' | 'request_more_evidence'>
  >({})
  const [decisionBusyKey, setDecisionBusyKey] = useState<string | null>(null)
  const [success, setSuccess] = useState('')

  const allergyList = useMemo(
    () =>
      allergies
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean),
    [allergies],
  )

  const missingIndications = useMemo(
    () => confirmedMedicines.filter((m) => !(m.verified_indication || '').trim()),
    [confirmedMedicines],
  )

  const patientContext = () => ({
    allergy_status: allergyStatus,
    allergies: allergyList,
    conditions: [] as string[],
    current_medicines: [] as string[],
  })

  const medicinePayload = (m: ConfirmedMedicine) => ({
    prescription_item_id: m.id,
    medicine_name: m.name,
    strength: m.strength,
    form: m.form,
    route: m.route,
    pharmacist_verified: true,
    verified_indication: (m.verified_indication || '').trim() || undefined,
    identity_confirmed_by_pharmacist: true,
  })

  const mergeResults = (data: EvaluationResponse) => {
    setEvalsByMedicine((prev) => {
      const next = { ...prev }
      for (const result of data.medicine_results) {
        next[result.prescription_item_id] = {
          evaluationId: data.evaluation_id,
          demoLabel: data.demo_label,
          result,
        }
      }
      return next
    })
  }

  const runEvaluateOne = async (medicine: ConfirmedMedicine) => {
    if (!(medicine.verified_indication || '').trim()) {
      setError(
        `Select a verified indication in the HITL table for #${medicine.item_number} ${medicine.name} before evaluating.`,
      )
      return
    }
    setBusyId(medicine.id)
    setError('')
    try {
      const { data } = await api.post<EvaluationResponse>('/api/v1/therapeutic-alternatives/evaluate', {
        prescription_id: sessionId,
        use_confirmed_session_medicines: false,
        top_n: 5,
        patient_context: patientContext(),
        prescribed_medicines: [medicinePayload(medicine)],
      })
      mergeResults(data)
      onDecisionChange?.()
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
      setError(formatApiDetail(detail) || `Evaluation failed for ${medicine.name}.`)
    } finally {
      setBusyId(null)
    }
  }

  const runEvaluateAll = async () => {
    if (missingIndications.length) {
      setError(
        `Select verified indications in the HITL table first: ${missingIndications
          .map((m) => `#${m.item_number} ${m.name}`)
          .join(', ')}.`,
      )
      return
    }
    setBusyId('__all__')
    setError('')
    try {
      const { data } = await api.post<EvaluationResponse>('/api/v1/therapeutic-alternatives/evaluate', {
        prescription_id: sessionId,
        use_confirmed_session_medicines: true,
        top_n: 5,
        patient_context: patientContext(),
        prescribed_medicines: confirmedMedicines.map(medicinePayload),
      })
      mergeResults(data)
      onDecisionChange?.()
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
      setError(formatApiDetail(detail) || 'Therapeutic alternatives evaluation failed.')
    } finally {
      setBusyId(null)
    }
  }

  const decide = async (
    evaluationId: string,
    prescriptionItemId: string,
    candidate: Candidate,
    action: 'accept_for_review' | 'reject' | 'request_more_evidence',
  ) => {
    const key = `${prescriptionItemId}:${candidate.candidate_drug_id}`
    const reason = (decisionReason[key] || '').trim()
    if ((action === 'reject' || action === 'request_more_evidence') && !reason) {
      setError('Pharmacist reasoning is required when rejecting or requesting more evidence.')
      setSuccess('')
      return
    }
    if (!evaluationId) {
      setError('Missing evaluation id. Re-run Evaluate candidates, then try again.')
      setSuccess('')
      return
    }
    setDecisionBusyKey(key)
    setError('')
    setSuccess('')
    try {
      await api.post(`/api/v1/therapeutic-alternatives/${evaluationId}/decision`, {
        prescription_item_id: prescriptionItemId,
        candidate_drug_id: candidate.candidate_drug_id,
        candidate_name: candidate.candidate_name,
        candidate_type: candidate.candidate_type || null,
        action,
        reason:
          action === 'accept_for_review'
            ? reason || 'Accepted for further pharmacist review'
            : reason,
        evidence_ids: (candidate.source_claims || []).map((c) => c.claim_id).filter(Boolean),
      })
      setDecisionStatus((all) => ({ ...all, [key]: action }))
      setSuccess(
        action === 'reject'
          ? `Rejected ${candidate.candidate_name} (reason saved).`
          : action === 'request_more_evidence'
            ? `Requested more evidence for ${candidate.candidate_name}.`
            : `Accepted ${candidate.candidate_name} for further review.`,
      )
      onDecisionChange?.()
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(
        typeof detail === 'string'
          ? detail
          : 'Could not save pharmacist decision. Re-evaluate if the session expired, then retry.',
      )
    } finally {
      setDecisionBusyKey(null)
    }
  }

  if (!confirmedMedicines.length) {
    return (
      <Alert severity="info">
        Therapeutic alternatives run only for pharmacist-confirmed medicines. Confirm rows in the HITL table first
        (including a dataset verified indication for each drug).
      </Alert>
    )
  }

  const busy = busyId !== null

  return (
    <Stack spacing={2} sx={{ width: '100%' }}>
      <Typography variant="h6">Candidate alternatives for pharmacist review</Typography>
      <Alert severity="warning">
        Decision-support only. Product candidates (same active moiety) and therapeutic candidates
        (different active ingredient) are listed separately. Neither list is an approved substitution
        or proof of clinical interchangeability. A licensed pharmacist must verify indication,
        patient context, dose, contraindications, interactions and applicable clinical guidance.
      </Alert>
      <Alert severity="info">
        Confirm each medicine in the HITL table first. Candidate search runs only after confirmation.
        Accept for review / Reject / Request more evidence — Reject and Request more evidence require a reason.
      </Alert>
      {success && <Alert severity="success">{success}</Alert>}
      {error && <Alert severity="error">{error}</Alert>}

      <Box sx={{ border: 1, borderColor: 'divider', borderRadius: 2, p: 2 }}>
        <Typography variant="subtitle2" gutterBottom>
          Patient allergy context (shared)
        </Typography>
        <Box
          sx={{
            display: 'grid',
            gap: 2,
            gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' },
            width: '100%',
          }}
        >
          <FormControl fullWidth>
            <InputLabel id="allergy-status-label">Allergy status</InputLabel>
            <Select
              labelId="allergy-status-label"
              label="Allergy status"
              value={allergyStatus}
              onChange={(e) => setAllergyStatus(String(e.target.value))}
            >
              <MenuItem value="none_known">none_known</MenuItem>
              <MenuItem value="documented">documented</MenuItem>
              <MenuItem value="unknown">unknown</MenuItem>
            </Select>
          </FormControl>
          <TextField
            label="Allergies (comma-separated)"
            value={allergies}
            onChange={(e) => setAllergies(e.target.value)}
            placeholder="e.g. penicillin"
            fullWidth
            disabled={allergyStatus !== 'documented'}
            helperText={allergyStatus === 'documented' ? 'Required when status is documented' : ' '}
          />
        </Box>
      </Box>

      {missingIndications.length > 0 && (
        <Alert severity="warning">
          Some confirmed medicines are missing a HITL verified indication:{' '}
          {missingIndications.map((m) => `#${m.item_number} ${m.name}`).join(', ')}.
        </Alert>
      )}

      {confirmedMedicines.map((medicine) => {
        const evalState = evalsByMedicine[medicine.id]
        const result = evalState?.result
        const label = `#${medicine.item_number} ${medicine.name}${medicine.strength ? ` ${medicine.strength}` : ''}`

        return (
          <Box
            key={medicine.id}
            sx={{ border: 1, borderColor: 'divider', borderRadius: 2, p: 2, width: '100%' }}
          >
            <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap mb={1}>
              <Typography variant="subtitle1" fontWeight={700}>
                Prescribed medicine: {label}
              </Typography>
              <Chip size="small" color="success" label="Confirmed" />
              {medicine.verified_indication ? (
                <Chip size="small" color="info" label={`Indication: ${medicine.verified_indication}`} />
              ) : (
                <Chip size="small" color="warning" label="Indication missing in HITL" />
              )}
              {evalState?.demoLabel && <ProvenanceChip label={evalState.demoLabel} />}
            </Stack>

            <Button
              variant="contained"
              color="secondary"
              disabled={busy || !medicine.verified_indication}
              onClick={() => void runEvaluateOne(medicine)}
              sx={{ mb: 1.5 }}
            >
              {busyId === medicine.id ? 'Evaluating…' : 'Evaluate alternatives for this medicine'}
            </Button>

            {result && (
              <Box mt={1}>
                <Typography variant="body2" color="text.secondary" mb={1}>
                  Status: {result.evaluation_status}
                </Typography>
                {result.source_medicine?.normalisation_suggestion && (
                  <Alert severity="info" sx={{ mb: 1 }}>
                    {result.source_medicine.normalisation_suggestion.ui_label ||
                      'Suggested normalisation — pharmacist confirmation required'}
                    : OCR/input «{result.source_medicine.ocr_value || result.source_medicine.normalisation_suggestion.input_value || '—'}»
                    → suggested «{result.source_medicine.normalisation_suggestion.canonical_value || '—'}»
                    ({result.source_medicine.normalisation_suggestion.match_method}, confidence{' '}
                    {result.source_medicine.normalisation_suggestion.confidence ?? '—'}). Confirmed:{' '}
                    {result.source_medicine.pharmacist_confirmed_value || result.source_medicine.medicine_name}
                  </Alert>
                )}
                {(result.missing_information?.length > 0 ||
                  statusHelp(result.evaluation_status, result.missing_information || [])) && (
                  <Alert severity="warning" sx={{ mb: 1 }}>
                    {statusHelp(result.evaluation_status, result.missing_information || []) ||
                      result.missing_information.join(' · ')}
                  </Alert>
                )}

                <Typography variant="subtitle1" fontWeight={700} gutterBottom>
                  Product Candidates
                </Typography>
                <Typography variant="body2" color="text.secondary" mb={1}>
                  Same-active-moiety product candidates (mandatory filters applied before scoring).
                </Typography>
                {!(result.product_candidates || []).length && (
                  <Typography variant="body2" color="text.secondary" mb={1}>
                    No eligible same-active-moiety product candidates after mandatory filters.
                  </Typography>
                )}
                <Stack spacing={1.5} mb={2}>
                  {(result.product_candidates || []).map((cand) => {
                    const key = `${result.prescription_item_id}:${cand.candidate_drug_id}`
                    return (
                      <CandidateCard
                        key={`prod-${cand.candidate_drug_id}`}
                        prescriptionItemId={result.prescription_item_id}
                        evaluationId={evalState.evaluationId}
                        cand={cand}
                        decisionReason={decisionReason[key] || ''}
                        decisionStatus={decisionStatus[key] || null}
                        decisionBusy={decisionBusyKey === key}
                        onReason={(v) => setDecisionReason((all) => ({ ...all, [key]: v }))}
                        onDecide={(action) =>
                          void decide(evalState.evaluationId, result.prescription_item_id, cand, action)
                        }
                      />
                    )
                  })}
                </Stack>

                <Typography variant="subtitle1" fontWeight={700} gutterBottom>
                  Therapeutic Candidates
                </Typography>
                <Alert severity="warning" sx={{ mb: 1 }}>
                  Different active ingredient — pharmacist assessment required
                </Alert>
                {!(result.therapeutic_candidates || result.eligible_alternatives || []).length &&
                  result.evaluation_status === 'completed' && (
                    <Typography variant="body2" color="text.secondary" mb={1}>
                      No eligible different-active-ingredient therapeutic candidates with overlapping
                      indication evidence were ranked for this verified indication.
                    </Typography>
                  )}
                <Stack spacing={1.5}>
                  {(result.therapeutic_candidates || result.eligible_alternatives || []).map((cand) => {
                    const key = `${result.prescription_item_id}:${cand.candidate_drug_id}`
                    return (
                      <CandidateCard
                        key={`ther-${cand.candidate_drug_id}`}
                        prescriptionItemId={result.prescription_item_id}
                        evaluationId={evalState.evaluationId}
                        cand={{
                          ...cand,
                          candidate_type: cand.candidate_type || 'DIFFERENT_ACTIVE_INGREDIENT',
                          warning_banner:
                            cand.warning_banner ||
                            'Different active ingredient — pharmacist assessment required',
                        }}
                        decisionReason={decisionReason[key] || ''}
                        decisionStatus={decisionStatus[key] || null}
                        decisionBusy={decisionBusyKey === key}
                        onReason={(v) => setDecisionReason((all) => ({ ...all, [key]: v }))}
                        onDecide={(action) =>
                          void decide(evalState.evaluationId, result.prescription_item_id, cand, action)
                        }
                      />
                    )
                  })}
                </Stack>

                {(result.blocked_candidates?.length > 0 || result.withdrawn_candidates?.length > 0) && (
                  <Box mt={2}>
                    <Typography variant="subtitle2">Excluded candidates</Typography>
                    {[...(result.blocked_candidates || []), ...(result.withdrawn_candidates || [])].map(
                      (cand) => (
                        <Typography key={cand.candidate_drug_id} variant="body2" color="text.secondary">
                          {cand.candidate_name} · {cand.status}
                        </Typography>
                      ),
                    )}
                  </Box>
                )}
              </Box>
            )}
          </Box>
        )
      })}

      <Button
        variant="outlined"
        color="secondary"
        disabled={busy || missingIndications.length > 0}
        onClick={() => void runEvaluateAll()}
      >
        {busyId === '__all__' ? 'Evaluating all…' : 'Evaluate alternatives for all confirmed medicines'}
      </Button>

      {success && <Alert severity="success">{success}</Alert>}
      {error && <Alert severity="error">{error}</Alert>}
    </Stack>
  )
}
