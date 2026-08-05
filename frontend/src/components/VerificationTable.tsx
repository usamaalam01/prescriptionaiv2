import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Alert,
  Autocomplete,
  Box,
  Button,
  Chip,
  FormControl,
  IconButton,
  Link,
  MenuItem,
  Paper,
  Popover,
  Select,
  Snackbar,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
  useMediaQuery,
  useTheme,
} from '@mui/material'
import { api } from '../api'

/** Catalog-safe Unable-to-verify reason codes (no invented SIG values). */
const UNABLE_PRESETS: Array<{ code: string; label: string }> = [
  { code: 'no_catalog_route', label: 'No matching catalog route' },
  { code: 'no_catalog_strength', label: 'No matching catalog strength' },
  { code: 'no_spl_dose', label: 'No SPL dose options for this selection' },
  { code: 'no_spl_frequency', label: 'No SPL frequency options for this selection' },
  { code: 'ambiguous_ocr', label: 'Ambiguous / unreadable OCR' },
  { code: 'wrong_drug_match', label: 'Catalog drug match unclear' },
  { code: 'other', label: 'Other (add note)' },
]

const FIELD_LABELS: Record<string, string> = {
  drug: 'Drug',
  route: 'Route',
  strength: 'Strength',
  dose: 'Dosage',
  frequency: 'Frequency',
  indication: 'Indication',
}

export interface DrugOption {
  formulary_id?: string
  canonical_name: string
  match_score?: number
  match_reason?: string
  suggested?: boolean
  source?: string
  matched_alias?: string
}

function sourceBadgeColor(src: string): 'default' | 'primary' | 'success' | 'warning' {
  const u = src.toUpperCase()
  if (u.includes('DRUGBANK')) return 'primary'
  if (u.includes('SPL')) return 'success'
  if (u.includes('NDC')) return 'warning'
  return 'default'
}

function SourceBadges({ source }: { source?: string | null }) {
  if (!source) return null
  const parts = source.split('+').map((s) => s.trim()).filter(Boolean)
  return (
    <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap sx={{ mt: 0.25 }}>
      {parts.map((p) => (
        <Chip key={p} size="small" label={p} color={sourceBadgeColor(p)} variant="outlined" sx={{ height: 20 }} />
      ))}
    </Stack>
  )
}

export interface IndicationOption {
  value: string
  sources?: string[]
  source_record_ids?: string[]
}

export interface EvidenceCitation {
  source: string
  source_id: string
  title: string
  url: string
  excerpt: string
}

export type FieldUiTone = 'amber' | 'yellow' | 'locked' | 'blocked'

export interface FieldState {
  value: string | null
  ai_value?: string | null
  status: 'green' | 'red'
  locked: boolean
  /** amber = OCR/mismatch; yellow = dataset match; blocked = cascade lock; locked = confirmed */
  ui_tone?: FieldUiTone
  options: Array<string | DrugOption | IndicationOption>
  message?: string | null
  optional?: boolean
  option_source?: string | null
  evidence_tier?: string | null
  catalog_sources?: string[]
  depends_on?: string[]
  options_context?: Record<string, unknown>
}

export interface EvidencePanel {
  drug_name: string
  therapeutic_class: string
  why_used: string
  limitations: string
  citations: EvidenceCitation[]
  knowledge_mode: string
  provenance_label?: string
  catalog_sources?: string[]
  routes?: string[]
  dosage_forms?: string[]
  strengths_sample?: string[]
}

export interface VerificationRow {
  medicine_id: string
  item_number: number
  confidence: number
  pharmacist_status: string
  can_confirm: boolean
  confirm_hint?: string | null
  confirm_disclaimer?: string | null
  validation_scope?: string | null
  thin_brand_shell?: boolean
  next_field?: 'drug' | 'strength' | 'route' | 'dose' | 'frequency' | 'indication' | null
  canonical_drug?: string | null
  evidence?: EvidencePanel | null
  awaiting_pharmacist_confirm?: boolean
  ocr_is_mock?: boolean
  confirm_blocked_mock_ocr?: boolean
  confirm_block_reason?: string | null
  fields: {
    drug: FieldState
    strength: FieldState
    route: FieldState
    dose: FieldState
    frequency: FieldState
    indication: FieldState
  }
}

/** HITL cell palette (status → light bg + text/border) */
const HITL_COLORS = {
  incorrect: { bg: '#FDECEC', fg: '#9B1C1C' },
  matched: { bg: '#FFF4D6', fg: '#7A4B00' },
  confirmed: { bg: '#E6F6EA', fg: '#176B35' },
  blocked: { bg: '#F3F4F6', fg: '#6B7280' },
} as const

function fieldTone(
  field: FieldState | undefined,
  rowResolved: boolean,
): 'incorrect' | 'matched' | 'confirmed' | 'blocked' {
  if (rowResolved) return 'confirmed'
  if (!field) return 'blocked'
  const tone = field.ui_tone ?? (field.locked ? 'blocked' : field.status === 'green' ? 'yellow' : 'amber')
  if (tone === 'locked') return 'confirmed'
  if (tone === 'blocked') return 'blocked'
  if (tone === 'yellow') return 'matched'
  return 'incorrect'
}

/** Normalize API row so every cascade field exists (OCR visible even when locked). */
function ensureFields(row: VerificationRow): VerificationRow['fields'] {
  const empty = (ai?: string | null): FieldState => ({
    value: ai || null,
    ai_value: ai || null,
    status: 'red',
    locked: true,
    ui_tone: 'blocked',
    options: [],
    message: undefined,
  })
  const f = row.fields || ({} as VerificationRow['fields'])
  return {
    drug: f.drug || empty(row.fields?.drug?.ai_value),
    route: f.route || empty(null),
    strength: f.strength || empty(null),
    dose: f.dose || empty(null),
    frequency: f.frequency || empty(null),
    indication: f.indication || {
      value: null,
      ai_value: null,
      status: 'red',
      locked: true,
      ui_tone: 'blocked',
      options: [],
      optional: true,
    },
  }
}

function cellSx(field: FieldState | undefined, rowResolved: boolean) {
  const tone = fieldTone(field, rowResolved)
  const { bg, fg } = HITL_COLORS[tone]
  return {
    bgcolor: bg,
    borderLeft: `4px solid ${fg}`,
    color: fg,
    transition: 'background-color 0.2s ease, border-color 0.2s ease',
    '& .MuiTypography-root, & .MuiFormHelperText-root, & .MuiInputBase-root': {
      color: 'inherit',
    },
    '& .MuiOutlinedInput-notchedOutline': {
      borderColor: `${fg}66`,
    },
  }
}

function isRowResolved(row: VerificationRow): boolean {
  return (
    row.pharmacist_status === 'confirmed' ||
    row.pharmacist_status === 'unidentified' ||
    row.pharmacist_status === 'excluded'
  )
}

/** Within a row: field is only interactive when unlocked by prior dataset matches */
function isFieldAccessible(field: FieldState | undefined, rowDisabled: boolean): boolean {
  if (rowDisabled || !field) return false
  return !field.locked
}

/** Read-only preview when cascade has not unlocked this field yet */
function BlockedFieldPreview({
  field,
}: {
  label?: string
  field: FieldState | undefined
}) {
  const ocr = field?.ai_value
  const val = field?.value
  return (
    <Typography
      variant="body2"
      sx={{ fontWeight: 600, fontSize: '0.8125rem', wordBreak: 'break-word', opacity: 0.85 }}
    >
      {ocr || val || '—'}
    </Typography>
  )
}

/** Immutable display for pharmacist-confirmed fields */
function LockedValue({ value }: { label?: string; value: string | null | undefined }) {
  return (
    <Typography
      variant="body2"
      sx={{ fontWeight: 600, fontSize: '0.8125rem', wordBreak: 'break-word', color: HITL_COLORS.confirmed.fg }}
    >
      {value || '—'}
    </Typography>
  )
}

const FORBIDDEN_PLACEHOLDERS = new Set([
  'unknown',
  'n/a',
  'na',
  'n.a.',
  'none',
  'null',
  'not known',
  'not known.',
  'unspecified',
  'not specified',
  'unable to verify',
  'tbd',
  '?',
  '-',
  '--',
])

function isForbiddenPlaceholder(value: string | null | undefined): boolean {
  if (!value) return false
  return FORBIDDEN_PLACEHOLDERS.has(value.trim().toLowerCase().replace(/\s+/g, ' '))
}

function asDrugOptions(options: FieldState['options']): DrugOption[] {
  return options
    .map((opt) => {
      if (typeof opt === 'string') return { canonical_name: opt, suggested: false, match_score: 0 }
      if ('canonical_name' in opt) return opt
      return { canonical_name: opt.value, suggested: false, match_score: 0 }
    })
    .filter((o) => !isForbiddenPlaceholder(o.canonical_name))
}

function asStringOptions(options: FieldState['options']): string[] {
  return options
    .map((opt) => {
      if (typeof opt === 'string') return opt
      if ('canonical_name' in opt) return opt.canonical_name
      return opt.value
    })
    .filter((v) => !isForbiddenPlaceholder(v))
}

function asIndicationOptions(options: FieldState['options']): IndicationOption[] {
  const out: IndicationOption[] = []
  for (const opt of options) {
    if (typeof opt === 'string') {
      if (isForbiddenPlaceholder(opt)) continue
      out.push({ value: opt, sources: [] })
    } else if ('canonical_name' in opt) {
      if (isForbiddenPlaceholder(opt.canonical_name)) continue
      out.push({ value: opt.canonical_name, sources: [] })
    } else {
      if (isForbiddenPlaceholder(opt.value)) continue
      out.push({ value: opt.value, sources: opt.sources || [] })
    }
  }
  return out
}

export function VerificationTable({
  sessionId,
  rows,
  onUpdated,
}: {
  sessionId: string
  rows: VerificationRow[]
  onUpdated: (rows: VerificationRow[]) => void
}) {
  const theme = useTheme()
  const isMobile = useMediaQuery(theme.breakpoints.down('md'))
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')
  const [busyId, setBusyId] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [submitted, setSubmitted] = useState(false)
  const [resolveReason, setResolveReason] = useState<Record<string, string>>({})
  const [unablePreset, setUnablePreset] = useState<Record<string, string>>({})

  const refreshTable = async () => {
    const { data } = await api.get<{ rows: VerificationRow[] }>(
      `/api/v1/reviews/${sessionId}/verification-table`,
    )
    const remote = data.rows ?? []
    // Never unlock a locally confirmed row if a race returns stale non-confirmed state
    const merged = remote.map((remoteRow) => {
      const local = rows.find((r) => r.medicine_id === remoteRow.medicine_id)
      if (local?.pharmacist_status === 'confirmed' && remoteRow.pharmacist_status !== 'confirmed') {
        return local
      }
      return remoteRow
    })
    onUpdated(merged)
  }

  const applyField = async (
    medicineId: string,
    field: keyof VerificationRow['fields'],
    value: string,
  ) => {
    // Allow clearing optional indication (empty string)
    if (!value && field !== 'indication') return
    const row = rows.find((r) => r.medicine_id === medicineId)
    if (!row || isRowResolved(row)) {
      setError('This medicine row is already resolved.')
      return
    }
    const fieldState = row.fields[field]
    if (fieldState?.locked) {
      setError('Complete the prior field (dataset match) before editing this one.')
      return
    }
    setError('')
    setBusyId(medicineId)
    try {
      const { data: updated } = await api.post<VerificationRow>(
        `/api/v1/reviews/${sessionId}/medicines/${medicineId}/fields`,
        { field, value },
      )
      onUpdated(rows.map((r) => (r.medicine_id === medicineId ? updated : r)))
      if (field === 'drug') {
        setInfo(
          `Drug updated for medicine #${row.item_number}. Route / strength / dosage / frequency cleared — reselect from catalog.`,
        )
      }
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        'Could not apply field correction.'
      setError(typeof detail === 'string' ? detail : 'Could not apply field correction.')
    } finally {
      setBusyId(null)
    }
  }

  const confirmRow = async (medicineId: string) => {
    setError('')
    setBusyId(medicineId)
    try {
      const { data: updated } = await api.post<VerificationRow>(
        `/api/v1/reviews/${sessionId}/medicines/${medicineId}/confirm-fields`,
      )
      onUpdated(rows.map((r) => (r.medicine_id === medicineId ? updated : r)))
      void refreshTable().catch(() => undefined)
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        'Confirm blocked until all fields are green.'
      setError(typeof detail === 'string' ? detail : 'Confirm blocked until all fields are green.')
      void refreshTable().catch(() => undefined)
    } finally {
      setBusyId(null)
    }
  }

  const resolveUnableToVerify = async (medicineId: string) => {
    const preset = unablePreset[medicineId] || ''
    const note = (resolveReason[medicineId] || '').trim()
    const presetLabel = UNABLE_PRESETS.find((p) => p.code === preset)?.label
    const trimmed = presetLabel
      ? note
        ? `${presetLabel}: ${note}`
        : presetLabel
      : note
    if (!trimmed) {
      setError('Select a reason code (or add a note) when marking Unable to verify.')
      return
    }
    if (preset === 'other' && !note) {
      setError('Add a short note when reason is Other.')
      return
    }
    setBusyId(medicineId)
    setError('')
    try {
      await api.post(`/api/v1/reviews/${sessionId}/medicines/${medicineId}/verify`, {
        status: 'excluded',
        reason: trimmed,
      })
      void refreshTable().catch(() => undefined)
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(typeof detail === 'string' ? detail : 'Could not save resolution.')
    } finally {
      setBusyId(null)
    }
  }

  const nextOpenItem = useMemo(() => {
    const firstOpen = rows.find((r) => !isRowResolved(r))
    return firstOpen?.item_number ?? null
  }, [rows])

  const allResolved = rows.length > 0 && rows.every((r) => isRowResolved(r))
  const confirmedCount = rows.filter((r) => r.pharmacist_status === 'confirmed').length

  const submitSession = async () => {
    if (!allResolved) {
      setError('Resolve every medicine (Confirm or Unable to verify) before Submit.')
      return
    }
    setSubmitting(true)
    setError('')
    try {
      const { data } = await api.post<{
        message?: string
        confirmed?: number
        excluded?: number
        total?: number
      }>(`/api/v1/reviews/${sessionId}/submit`)
      setSubmitted(true)
      setInfo(
        data.message ||
          `Submitted: ${data.confirmed ?? confirmedCount} confirmed, ${data.excluded ?? 0} unable to verify.`,
      )
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(typeof detail === 'string' ? detail : 'Could not submit verification.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Stack spacing={2} sx={{ width: '100%', maxWidth: '100%', overflowX: 'hidden' }}>
      <Typography variant="h6">Pharmacist verification (HITL)</Typography>
      <Alert severity="info">
        Confirm each medicine (Drug → Route → Strength → Dosage → Frequency). Indication is optional
        for Confirm. Options come from the catalog only — use Unable to verify when a field cannot be
        matched.
      </Alert>
      {rows.some((r) => r.confirm_blocked_mock_ocr) && (
        <Alert severity="warning">
          {rows.find((r) => r.confirm_block_reason)?.confirm_block_reason ||
            'MOCK OCR — Confirm is blocked for clinical-safety integrity.'}
        </Alert>
      )}
      {error && (
        <Alert severity="error" onClose={() => setError('')}>
          {error}
        </Alert>
      )}
      {rows.length === 0 && (
        <Alert severity="warning">
          No medicine rows for HITL yet. Re-run the pipeline after upload.
        </Alert>
      )}

      {isMobile ? (
        <Stack spacing={2}>
          {rows.map((row) => (
            <MedicineCard
              key={row.medicine_id}
              row={row}
              busy={busyId === row.medicine_id}
              recommended={row.item_number === nextOpenItem && !isRowResolved(row)}
              unablePreset={unablePreset[row.medicine_id] || ''}
              resolveReason={resolveReason[row.medicine_id] || ''}
              onUnablePreset={(v) =>
                setUnablePreset((all) => ({ ...all, [row.medicine_id]: v }))
              }
              onResolveReason={(v) =>
                setResolveReason((all) => ({ ...all, [row.medicine_id]: v }))
              }
              onApply={(field, value) => void applyField(row.medicine_id, field, value)}
              onConfirm={() => void confirmRow(row.medicine_id)}
              onUnable={() => void resolveUnableToVerify(row.medicine_id)}
            />
          ))}
        </Stack>
      ) : (
        <Box sx={{ width: '100%', overflowX: 'auto' }}>
          <Table
            size="small"
            sx={{
              width: '100%',
              minWidth: 980,
              tableLayout: 'fixed',
              '& td, & th': {
                wordBreak: 'break-word',
                whiteSpace: 'normal',
                verticalAlign: 'top',
                px: 1,
                py: 1,
              },
            }}
          >
            <TableHead>
              <TableRow>
                <TableCell sx={{ width: '4%' }}>#</TableCell>
                <TableCell sx={{ width: '18%' }}>Drug</TableCell>
                <TableCell sx={{ width: '11%' }}>Route</TableCell>
                <TableCell sx={{ width: '13%' }}>Strength</TableCell>
                <TableCell sx={{ width: '13%' }}>Dosage</TableCell>
                <TableCell sx={{ width: '13%' }}>Frequency</TableCell>
                <TableCell sx={{ width: '14%' }}>Indication</TableCell>
                <TableCell sx={{ width: '14%' }}>Status</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {rows.map((row) => {
                const fields = ensureFields(row)
                const confirmed = row.pharmacist_status === 'confirmed'
                const resolved = isRowResolved(row)
                const disabled = resolved || busyId === row.medicine_id
                const recommended = !resolved && row.item_number === nextOpenItem

                return (
                  <TableRow
                    key={row.medicine_id}
                    hover={!resolved}
                    sx={
                      confirmed
                        ? { bgcolor: HITL_COLORS.confirmed.bg }
                        : recommended
                          ? { boxShadow: 'inset 0 0 0 2px #7A4B00' }
                          : resolved
                            ? { bgcolor: '#FAFAFA' }
                            : undefined
                    }
                  >
                    <TableCell>{row.item_number}</TableCell>
                    <TableCell sx={cellSx(fields.drug, resolved)}>
                      {resolved ? (
                        <LockedValue value={fields.drug.value || row.canonical_drug} label="Drug" />
                      ) : (
                        <DrugDropdown
                          field={fields.drug}
                          evidence={fields.drug.status === 'green' ? row.evidence : null}
                          disabled={!isFieldAccessible(fields.drug, disabled)}
                          onSelect={(value) => void applyField(row.medicine_id, 'drug', value)}
                        />
                      )}
                    </TableCell>
                    <TableCell sx={cellSx(fields.route, resolved)}>
                      {resolved ? (
                        <LockedValue value={fields.route.value} label="Route" />
                      ) : !isFieldAccessible(fields.route, disabled) ? (
                        <BlockedFieldPreview label="Route" field={fields.route} />
                      ) : (
                        <CatalogSelect
                          label="Route"
                          field={fields.route}
                          disabled={false}
                          onSelect={(value) => void applyField(row.medicine_id, 'route', value)}
                        />
                      )}
                    </TableCell>
                    <TableCell sx={cellSx(fields.strength, resolved)}>
                      {resolved ? (
                        <LockedValue value={fields.strength.value} label="Strength" />
                      ) : !isFieldAccessible(fields.strength, disabled) ? (
                        <BlockedFieldPreview label="Strength" field={fields.strength} />
                      ) : (
                        <CatalogSelect
                          label="Strength"
                          field={fields.strength}
                          disabled={false}
                          onSelect={(value) => void applyField(row.medicine_id, 'strength', value)}
                        />
                      )}
                    </TableCell>
                    <TableCell sx={cellSx(fields.dose, resolved)}>
                      {resolved ? (
                        <LockedValue value={fields.dose.value} label="Dosage" />
                      ) : !isFieldAccessible(fields.dose, disabled) ? (
                        <BlockedFieldPreview label="Dosage" field={fields.dose} />
                      ) : (
                        <CatalogSelect
                          label="Dosage"
                          field={fields.dose}
                          disabled={false}
                          onSelect={(value) => void applyField(row.medicine_id, 'dose', value)}
                        />
                      )}
                    </TableCell>
                    <TableCell sx={cellSx(fields.frequency, resolved)}>
                      {resolved ? (
                        <LockedValue value={fields.frequency.value} label="Frequency" />
                      ) : !isFieldAccessible(fields.frequency, disabled) ? (
                        <BlockedFieldPreview label="Frequency" field={fields.frequency} />
                      ) : (
                        <CatalogSelect
                          label="Frequency"
                          field={fields.frequency}
                          disabled={false}
                          onSelect={(value) => void applyField(row.medicine_id, 'frequency', value)}
                        />
                      )}
                    </TableCell>
                    <TableCell sx={cellSx(fields.indication, resolved)}>
                      {resolved && !confirmed ? (
                        <LockedValue value={fields.indication.value || '(none)'} label="Indication" />
                      ) : confirmed && !fields.indication.locked ? (
                        <IndicationSelect
                          field={fields.indication}
                          disabled={busyId === row.medicine_id}
                          onSelect={(value) => void applyField(row.medicine_id, 'indication', value)}
                        />
                      ) : !isFieldAccessible(fields.indication, disabled) ? (
                        <BlockedFieldPreview label="Indication" field={fields.indication} />
                      ) : (
                        <IndicationSelect
                          field={fields.indication}
                          disabled={false}
                          onSelect={(value) => void applyField(row.medicine_id, 'indication', value)}
                        />
                      )}
                    </TableCell>
                    <TableCell>
                      <StatusActions
                        row={row}
                        fields={fields}
                        busy={busyId === row.medicine_id}
                        unablePreset={unablePreset[row.medicine_id] || ''}
                        resolveReason={resolveReason[row.medicine_id] || ''}
                        onUnablePreset={(v) =>
                          setUnablePreset((all) => ({ ...all, [row.medicine_id]: v }))
                        }
                        onResolveReason={(v) =>
                          setResolveReason((all) => ({ ...all, [row.medicine_id]: v }))
                        }
                        onConfirm={() => void confirmRow(row.medicine_id)}
                        onUnable={() => void resolveUnableToVerify(row.medicine_id)}
                      />
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </Box>
      )}

      {rows.length > 0 && (
        <Paper variant="outlined" sx={{ p: 2, bgcolor: '#F8FAFC' }}>
          <Stack spacing={1.5}>
            <Typography variant="subtitle1" fontWeight={700}>
              Submit prescription verification
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ lineHeight: 1.5 }}>
              Submit is for prescription drug validation against the trusted catalog (FDA_NDC /
              DrugBank / FDA_SPL). It is not a patient clinical record and does not capture allergy,
              age, pregnancy, or other patient-context data. Indication is optional here; therapeutic
              alternatives later may need an indication. Decision-support only — not a substitute for
              clinical judgment or full product labeling.
            </Typography>
            {!allResolved && (
              <Typography variant="caption" color="warning.main">
                Resolve all medicines first ({confirmedCount} confirmed ·{' '}
                {rows.filter((r) => isRowResolved(r)).length}/{rows.length} resolved).
              </Typography>
            )}
            {submitted && (
              <Alert severity="success">
                Verification submitted for this prescription session.
              </Alert>
            )}
            <Box>
              <Button
                variant="contained"
                color="primary"
                size="large"
                disabled={!allResolved || submitting || submitted}
                onClick={() => void submitSession()}
              >
                {submitted ? 'Submitted' : submitting ? 'Submitting…' : 'Submit'}
              </Button>
            </Box>
          </Stack>
        </Paper>
      )}

      <Snackbar
        open={Boolean(info)}
        autoHideDuration={5000}
        onClose={() => setInfo('')}
        message={info}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      />
    </Stack>
  )
}

function emptyOptionsAlert(fields: VerificationRow['fields']): string | null {
  const cascade: Array<keyof VerificationRow['fields']> = [
    'route',
    'strength',
    'dose',
    'frequency',
  ]
  for (const name of cascade) {
    const f = fields[name]
    if (!f || f.locked) continue
    if (f.status === 'red' && (!f.options || f.options.length === 0)) {
      const label = FIELD_LABELS[name] || name
      return (
        f.message ||
        `No catalog ${label.toLowerCase()} options for this selection. Pick another catalog value upstream, or Unable to verify.`
      )
    }
  }
  return null
}

function StatusActions({
  row,
  fields,
  busy,
  unablePreset,
  resolveReason,
  onUnablePreset,
  onResolveReason,
  onConfirm,
  onUnable,
}: {
  row: VerificationRow
  fields: VerificationRow['fields']
  busy: boolean
  unablePreset: string
  resolveReason: string
  onUnablePreset: (v: string) => void
  onResolveReason: (v: string) => void
  onConfirm: () => void
  onUnable: () => void
}) {
  const confirmed = row.pharmacist_status === 'confirmed'
  const resolved = isRowResolved(row)
  const emptyHint = emptyOptionsAlert(fields)
  const nextLabel = row.next_field ? FIELD_LABELS[row.next_field] || row.next_field : null

  return (
    <Stack spacing={0.75} alignItems="flex-start" sx={{ width: '100%' }}>
      {(confirmed ||
        row.pharmacist_status === 'unidentified' ||
        row.pharmacist_status === 'excluded') && (
        <Chip
          size="small"
          color={
            confirmed
              ? 'success'
              : row.pharmacist_status === 'excluded' || row.pharmacist_status === 'unidentified'
                ? 'warning'
                : 'default'
          }
          label={
            confirmed
              ? 'Confirmed'
              : row.pharmacist_status === 'unidentified' || row.pharmacist_status === 'excluded'
                ? 'Unable to verify'
                : 'Queued'
          }
        />
      )}
      {confirmed ? (
        !(fields.indication.value || '').trim() ? (
          <Typography variant="caption" color="warning.main">
            Select indication above for therapeutic alternatives.
          </Typography>
        ) : null
      ) : row.thin_brand_shell ? (
        <Typography variant="caption" color="error.main">
          Thin catalog shell — pick a richer drug or Unable to verify.
        </Typography>
      ) : resolved ? null : (
        <Stack spacing={0.75} sx={{ width: '100%' }}>
          <Button
            size="small"
            variant="contained"
            color="success"
            disabled={!row.can_confirm || busy}
            onClick={onConfirm}
            aria-describedby={`confirm-hint-${row.medicine_id}`}
          >
            Confirm
          </Button>
          {!row.can_confirm && (
            <Typography
              id={`confirm-hint-${row.medicine_id}`}
              variant="caption"
              color="text.secondary"
              sx={{ lineHeight: 1.35 }}
            >
              {row.confirm_hint ||
                (nextLabel
                  ? `Next: select catalog ${nextLabel}.`
                  : 'Complete Drug → Route → Strength → Dosage → Frequency to confirm.')}
              {nextLabel ? (
                <>
                  {' '}
                  <Box component="span" sx={{ fontWeight: 700, color: HITL_COLORS.matched.fg }}>
                    Next field: {nextLabel}
                  </Box>
                </>
              ) : null}
            </Typography>
          )}
          {emptyHint && (
            <Alert severity="warning" sx={{ py: 0.25, px: 1, width: '100%' }}>
              <Typography variant="caption" sx={{ display: 'block', lineHeight: 1.35 }}>
                {emptyHint}
              </Typography>
            </Alert>
          )}
          <FormControl size="small" fullWidth>
            <Select
              displayEmpty
              value={unablePreset}
              onChange={(e) => onUnablePreset(String(e.target.value))}
              renderValue={(selected) =>
                selected
                  ? UNABLE_PRESETS.find((p) => p.code === selected)?.label || selected
                  : 'Unable reason (catalog-safe)…'
              }
            >
              {UNABLE_PRESETS.map((p) => (
                <MenuItem key={p.code} value={p.code} dense>
                  {p.label}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <TextField
            size="small"
            label="Note (optional except Other)"
            value={resolveReason}
            onChange={(e) => onResolveReason(e.target.value)}
            fullWidth
            multiline
            minRows={1}
          />
          <Button
            size="small"
            variant="outlined"
            color="warning"
            disabled={busy}
            onClick={onUnable}
          >
            Unable to verify
          </Button>
        </Stack>
      )}
    </Stack>
  )
}

function MedicineCard({
  row,
  busy,
  recommended,
  unablePreset,
  resolveReason,
  onUnablePreset,
  onResolveReason,
  onApply,
  onConfirm,
  onUnable,
}: {
  row: VerificationRow
  busy: boolean
  recommended: boolean
  unablePreset: string
  resolveReason: string
  onUnablePreset: (v: string) => void
  onResolveReason: (v: string) => void
  onApply: (field: keyof VerificationRow['fields'], value: string) => void
  onConfirm: () => void
  onUnable: () => void
}) {
  const fields = ensureFields(row)
  const confirmed = row.pharmacist_status === 'confirmed'
  const resolved = isRowResolved(row)
  const disabled = resolved || busy

  return (
    <Paper
      variant="outlined"
      sx={{
        p: 1.5,
        borderColor: recommended ? HITL_COLORS.matched.fg : undefined,
        borderWidth: recommended ? 2 : 1,
        bgcolor: confirmed ? HITL_COLORS.confirmed.bg : undefined,
      }}
    >
      <Stack spacing={1.25}>
        <Stack direction="row" justifyContent="space-between" alignItems="center">
          <Typography variant="subtitle2">Medicine #{row.item_number}</Typography>
          {recommended && !resolved && (
            <Chip size="small" label="Suggested next" color="warning" variant="outlined" />
          )}
        </Stack>
        <Box sx={{ ...cellSx(fields.drug, resolved), p: 1, borderRadius: 1 }}>
          <Typography variant="caption" display="block" sx={{ mb: 0.5, fontWeight: 600 }}>
            Drug
          </Typography>
          {resolved ? (
            <LockedValue value={fields.drug.value || row.canonical_drug} />
          ) : (
            <DrugDropdown
              field={fields.drug}
              evidence={fields.drug.status === 'green' ? row.evidence : null}
              disabled={!isFieldAccessible(fields.drug, disabled)}
              onSelect={(value) => onApply('drug', value)}
            />
          )}
        </Box>
        {(
          [
            ['route', 'Route'],
            ['strength', 'Strength'],
            ['dose', 'Dosage'],
            ['frequency', 'Frequency'],
          ] as const
        ).map(([key, label]) => {
          const field = fields[key]
          return (
            <Box key={key} sx={{ ...cellSx(field, resolved), p: 1, borderRadius: 1 }}>
              <Typography variant="caption" display="block" sx={{ mb: 0.5, fontWeight: 600 }}>
                {label}
              </Typography>
              {resolved ? (
                <LockedValue value={field.value} />
              ) : !isFieldAccessible(field, disabled) ? (
                <BlockedFieldPreview field={field} />
              ) : (
                <CatalogSelect
                  label={label}
                  field={field}
                  disabled={false}
                  onSelect={(value) => onApply(key, value)}
                />
              )}
            </Box>
          )
        })}
        <Box sx={{ ...cellSx(fields.indication, resolved), p: 1, borderRadius: 1 }}>
          <Typography variant="caption" display="block" sx={{ mb: 0.5, fontWeight: 600 }}>
            Indication (optional)
          </Typography>
          {resolved && !confirmed ? (
            <LockedValue value={fields.indication.value || '(none)'} />
          ) : !isFieldAccessible(fields.indication, disabled) && !(confirmed && !fields.indication.locked) ? (
            <BlockedFieldPreview field={fields.indication} />
          ) : (
            <IndicationSelect
              field={fields.indication}
              disabled={busy && !confirmed}
              onSelect={(value) => onApply('indication', value)}
            />
          )}
        </Box>
        <StatusActions
          row={row}
          fields={fields}
          busy={busy}
          unablePreset={unablePreset}
          resolveReason={resolveReason}
          onUnablePreset={onUnablePreset}
          onResolveReason={onResolveReason}
          onConfirm={onConfirm}
          onUnable={onUnable}
        />
      </Stack>
    </Paper>
  )
}

function DrugDropdown({
  field,
  evidence,
  disabled,
  onSelect,
}: {
  field: FieldState
  evidence?: EvidencePanel | null
  disabled: boolean
  onSelect: (value: string) => void
}) {
  const seedOptions = useMemo(() => {
    // Dropdown must be trusted catalog only (FDA_NDC / DrugBank / FDA_SPL)
    const all = asDrugOptions(field.options)
    const trusted = all.filter((o) => {
      const src = (o.source || '').toUpperCase()
      return (
        src.includes('FDA') ||
        src.includes('NDC') ||
        src.includes('DRUGBANK') ||
        src.includes('SPL') ||
        // Keep current matched canonical even if source missing
        (field.status === 'green' && o.canonical_name === field.value)
      )
    })
    return trusted.length ? trusted : all.filter((o) => o.suggested !== false)
  }, [field.options, field.status, field.value])
  const [inputValue, setInputValue] = useState(field.value || '')
  const [options, setOptions] = useState<DrugOption[]>(seedOptions)
  const [loading, setLoading] = useState(false)
  const searchSeq = useRef(0)

  useEffect(() => {
    setOptions(seedOptions)
    setInputValue(field.value || '')
  }, [seedOptions, field.value])

  useEffect(() => {
    const q = inputValue.trim()
    // Keep seed/OCR suggestions when the box is empty or matches the current value
    if (q.length < 2) {
      setOptions(seedOptions)
      return
    }
    if (field.value && q === field.value && seedOptions.length > 0) {
      setOptions(seedOptions)
      return
    }

    const seq = ++searchSeq.current
    const timer = window.setTimeout(() => {
      setLoading(true)
      void api
        .get<{ options: DrugOption[] }>('/api/v1/formulary/suggest', {
          params: { q, limit: 20 },
        })
        .then((res) => {
          if (seq !== searchSeq.current) return
          const remote = asDrugOptions(res.data.options || [])
          // Prefer remote catalog hits; keep exact current value if missing
          const merged = [...remote]
          if (field.value && !merged.some((o) => o.canonical_name === field.value)) {
            const keep = seedOptions.find((o) => o.canonical_name === field.value)
            if (keep) merged.unshift(keep)
          }
          setOptions(merged.length ? merged : seedOptions)
        })
        .catch(() => {
          if (seq !== searchSeq.current) return
          // Client-filter seed options as last resort
          const low = q.toLowerCase()
          const filtered = seedOptions.filter((o) =>
            o.canonical_name.toLowerCase().includes(low),
          )
          setOptions(filtered.length ? filtered : seedOptions)
        })
        .finally(() => {
          if (seq === searchSeq.current) setLoading(false)
        })
    }, 220)

    return () => window.clearTimeout(timer)
  }, [inputValue, seedOptions, field.value])

  const selected =
    options.find((o) => o.canonical_name === field.value) ||
    seedOptions.find((o) => o.canonical_name === field.value) ||
    (field.value
      ? {
          canonical_name: field.value,
          suggested: field.status === 'green',
          match_score: field.status === 'green' ? 1 : 0,
        }
      : null)

  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null)
  const open = Boolean(anchorEl) && Boolean(evidence)

  return (
    <Stack spacing={0.75} sx={{ minWidth: 0, width: '100%' }}>
      {field.ai_value && (
        <Typography variant="caption" color="text.secondary">
          OCR: {field.ai_value}
        </Typography>
      )}

      <Stack direction="row" spacing={0.5} alignItems="flex-start" sx={{ width: '100%' }}>
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Autocomplete
            size="small"
            fullWidth
            disabled={disabled}
            options={options}
            loading={loading}
            openOnFocus
            autoHighlight
            filterOptions={(opts) => opts}
            inputValue={inputValue}
            onInputChange={(_e, value, reason) => {
              if (reason === 'reset' && field.value) {
                setInputValue(field.value)
                return
              }
              setInputValue(value)
            }}
            groupBy={() => 'Similar FDA / DrugBank matches'}
            getOptionLabel={(opt) => opt.canonical_name}
            isOptionEqualToValue={(a, b) => a.canonical_name === b.canonical_name}
            value={selected}
            onChange={(_e, value) => {
              if (value?.canonical_name) onSelect(value.canonical_name)
            }}
            noOptionsText={
              inputValue.trim().length < 2
                ? 'Type at least 2 letters to search verified FDA/DrugBank drugs'
                : loading
                  ? 'Searching catalog…'
                  : 'No similar FDA/DrugBank matches'
            }
            renderOption={(props, opt) => (
              <li {...props} key={`${opt.formulary_id || ''}-${opt.canonical_name}`}>
                <Stack sx={{ width: '100%', py: 0.25 }}>
                  <Typography sx={{ fontWeight: 700, fontSize: '0.75rem' }}>
                    {opt.canonical_name}
                  </Typography>
                  <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.65rem' }}>
                    {opt.match_reason || 'catalog'}
                    {opt.match_score != null && opt.match_score > 0
                      ? ` · ${(opt.match_score * 100).toFixed(0)}% match`
                      : ''}
                  </Typography>
                  <SourceBadges source={opt.source} />
                </Stack>
              </li>
            )}
            renderInput={(params) => (
              <TextField
                {...params}
                placeholder={
                  field.status === 'green' ? 'Matched — type to change' : 'Type to search catalog…'
                }
                error={field.status === 'red'}
                helperText={
                  field.status === 'green'
                    ? undefined
                    : field.message || 'Select the matching catalog drug'
                }
                InputProps={{
                  ...params.InputProps,
                  sx: {
                    fontWeight: 700,
                    fontSize: '0.75rem',
                    ...((params.InputProps as { sx?: object })?.sx || {}),
                  },
                }}
              />
            )}
          />
        </Box>
        {evidence && (
          <IconButton
            size="small"
            aria-label="Show catalog evidence"
            aria-expanded={open}
            aria-haspopup="dialog"
            onClick={(e) => setAnchorEl(open ? null : e.currentTarget)}
            sx={{ mt: 0.25 }}
          >
            <Typography component="span" sx={{ fontSize: '0.7rem', fontWeight: 800 }}>
              i
            </Typography>
          </IconButton>
        )}
      </Stack>
      {selected &&
        selected.suggested &&
        typeof selected.match_score === 'number' &&
        selected.match_score < 0.92 &&
        field.status !== 'green' && (
          <Alert severity="warning" sx={{ py: 0.25 }}>
            Fuzzy / look-alike risk (score {(selected.match_score * 100).toFixed(0)}%). Confirm the
            correct drug carefully before continuing.
          </Alert>
        )}

      <Popover
        open={open}
        anchorEl={anchorEl}
        onClose={() => setAnchorEl(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
        transformOrigin={{ vertical: 'top', horizontal: 'left' }}
        slotProps={{
          paper: {
            sx: {
              p: 2,
              maxWidth: { xs: '90vw', sm: 400 },
              bgcolor: '#F9FBE7',
              border: '1px solid #AED581',
            },
          },
        }}
      >
        {evidence && (
          <Stack spacing={1}>
            <Typography variant="subtitle2">
              {evidence.drug_name} · {evidence.therapeutic_class}
            </Typography>
            <Typography variant="body2">
              <strong>Catalog indication / use:</strong> {evidence.why_used}
            </Typography>
            <Typography variant="body2">
              <strong>Limitations:</strong> {evidence.limitations}
            </Typography>
            {(evidence.routes?.length ||
              evidence.dosage_forms?.length ||
              evidence.strengths_sample?.length) ? (
              <Typography variant="caption" display="block">
                {evidence.routes?.length ? `Routes: ${evidence.routes.join(', ')}. ` : ''}
                {evidence.dosage_forms?.length
                  ? `Forms: ${evidence.dosage_forms.slice(0, 4).join(', ')}. `
                  : ''}
                {evidence.strengths_sample?.length
                  ? `Strengths (sample): ${evidence.strengths_sample.slice(0, 4).join(', ')}.`
                  : ''}
              </Typography>
            ) : null}
            <Typography variant="caption" color="success.dark">
              {evidence.provenance_label || 'FDA_NDC + DrugBank + FDA_SPL catalog'}
            </Typography>
            {evidence.citations.map((c) => (
              <Typography key={`${c.source}-${c.source_id}`} variant="caption" display="block">
                [{c.source}]{' '}
                <Link href={c.url} target="_blank" rel="noreferrer">
                  {c.title}
                </Link>
                {' — '}
                {c.excerpt}
              </Typography>
            ))}
          </Stack>
        )}
      </Popover>
    </Stack>
  )
}

function IndicationSelect({
  field,
  disabled,
  onSelect,
}: {
  field: FieldState
  disabled: boolean
  onSelect: (value: string) => void
}) {
  const options = asIndicationOptions(field.options)
  const valueInList = field.value && options.some((o) => o.value === field.value) ? field.value : ''
  const selected = options.find((o) => o.value === valueInList)

  return (
    <Stack spacing={0.5} sx={{ minWidth: 0, width: '100%' }}>
      <FormControl size="small" fullWidth disabled={disabled} error={field.status === 'red' && !disabled}>
        <Select
          displayEmpty
          value={valueInList}
          onChange={(e) => onSelect(String(e.target.value))}
          renderValue={(selectedVal) => {
            if (!selectedVal) {
              return (
                <Typography sx={{ fontWeight: 500, fontSize: '0.75rem' }} color="text.secondary" noWrap>
                  {disabled ? '—' : field.optional ? 'Optional' : 'Select indication…'}
                </Typography>
              )
            }
            return (
              <Typography sx={{ fontWeight: 700, fontSize: '0.75rem' }} noWrap>
                {selectedVal}
              </Typography>
            )
          }}
        >
          {field.optional && (
            <MenuItem value="">
              <Typography sx={{ fontWeight: 700, fontSize: '0.75rem' }} color="text.secondary">
                Skip (Confirm OK · needed for alternatives)
              </Typography>
            </MenuItem>
          )}
          {options.map((opt) => (
            <MenuItem key={opt.value} value={opt.value} dense>
              <Stack spacing={0.25} sx={{ maxWidth: 320, py: 0.25 }}>
                <Typography sx={{ fontWeight: 700, fontSize: '0.75rem' }}>{opt.value}</Typography>
                {(opt.sources || []).length > 0 && (
                  <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
                    {(opt.sources || []).map((src) => (
                      <Chip
                        key={`${opt.value}-${src}`}
                        size="small"
                        label={src}
                        color={sourceBadgeColor(src)}
                        variant="outlined"
                        sx={{ height: 18 }}
                      />
                    ))}
                  </Stack>
                )}
              </Stack>
            </MenuItem>
          ))}
        </Select>
      </FormControl>
      {selected?.sources && selected.sources.length > 0 && (
        <SourceBadges source={selected.sources.join('+')} />
      )}
    </Stack>
  )
}

function CatalogSelect({
  label,
  field,
  disabled,
  onSelect,
}: {
  label: string
  field: FieldState
  disabled: boolean
  onSelect: (value: string) => void
}) {
  const baseOptions = asStringOptions(field.options)
  const optionsKey = `${label}:${baseOptions.join('|')}:${(field.depends_on || []).join('+')}`
  // Only keep a current value in the Select when it is already a green dataset match
  const options =
    field.value &&
    field.status === 'green' &&
    !baseOptions.some((o) => o === field.value)
      ? [field.value, ...baseOptions]
      : baseOptions
  const valueInList = field.value && options.includes(field.value) ? field.value : ''
  const matched = field.status === 'green'
  const fg = matched ? HITL_COLORS.matched.fg : HITL_COLORS.incorrect.fg
  const optionSx = { fontWeight: 700, fontSize: '0.75rem' } as const

  return (
    <Stack spacing={0.5} sx={{ minWidth: 0, width: '100%' }} key={optionsKey}>
      {field.ai_value && (
        <Typography variant="caption" sx={{ color: fg, opacity: 0.85 }}>
          OCR: {field.ai_value}
        </Typography>
      )}
      {!disabled && !options.length && (
        <Alert severity="warning" sx={{ py: 0.25, px: 1 }}>
          <Typography variant="caption" sx={{ display: 'block', lineHeight: 1.35 }}>
            {field.message ||
              `No catalog ${label.toLowerCase()} options. Change an upstream catalog field or use Unable to verify.`}
          </Typography>
        </Alert>
      )}
      <FormControl size="small" fullWidth disabled={disabled} error={!matched && !disabled}>
        <Select
          displayEmpty
          value={valueInList}
          onChange={(e) => onSelect(String(e.target.value))}
          renderValue={(selected) => {
            if (!selected) {
              if (field.ai_value && !disabled) {
                return (
                  <Typography sx={{ ...optionSx, color: HITL_COLORS.incorrect.fg }} noWrap>
                    {field.ai_value} (select match)
                  </Typography>
                )
              }
              return (
                <Typography sx={{ ...optionSx, color: HITL_COLORS.blocked.fg, fontWeight: 500 }} noWrap>
                  {disabled ? '—' : options.length ? `Select ${label.toLowerCase()}…` : 'No catalog options'}
                </Typography>
              )
            }
            return (
              <Typography sx={optionSx} noWrap>
                {selected}
              </Typography>
            )
          }}
        >
          {options.map((opt) => (
            <MenuItem key={opt} value={opt} dense>
              <Typography sx={optionSx}>{opt}</Typography>
            </MenuItem>
          ))}
        </Select>
      </FormControl>
    </Stack>
  )
}
