import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Alert,
  Box,
  Button,
  Chip,
  LinearProgress,
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

interface AnalyticsPayload {
  available: boolean
  message?: string
  demo_label?: string
  provenance_label?: string
  disclaimer?: string
  summary?: Record<string, number | null>
  text_metrics?: {
    full_prescription: Record<string, number | string | boolean | null>
    medicine_metrics: Array<Record<string, string | number | null>>
  }
  field_metrics?: Array<Record<string, string | number | null>>
  entity_metrics?: Array<Record<string, string | number | null>>
  entity_aggregates?: Record<string, number | string | boolean | null>
  entity_metrics_exact?: Array<Record<string, string | number | null>>
  entity_aggregates_exact?: Record<string, number | string | boolean | null>
  entity_metrics_normalized?: Array<Record<string, string | number | null>>
  entity_aggregates_normalized?: Record<string, number | string | boolean | null>
  alternative_metrics?: Record<string, unknown>
  comparison_rows?: Array<Record<string, string | boolean | null>>
  medicine_performance?: Array<Record<string, string | number | null>>
}

function fmtNum(v: number | null | undefined) {
  if (v == null) return 'Not available'
  return String(v)
}

function KpiCard({ label, value, accent }: { label: string; value: string; accent: string }) {
  return (
    <Box
      sx={{
        borderRadius: 2,
        p: 1.5,
        minWidth: 0,
        bgcolor: '#FAFBFC',
        border: '1px solid',
        borderColor: 'divider',
        borderTop: `4px solid ${accent}`,
      }}
    >
      <Typography variant="caption" color="text.secondary" display="block" noWrap title={label}>
        {label}
      </Typography>
      <Typography variant="h5" fontWeight={700} sx={{ lineHeight: 1.2, mt: 0.5 }}>
        {value}
      </Typography>
    </Box>
  )
}

/** Horizontal bar chart — best for single-metric field accuracy comparison */
function ExactMatchChart({
  items,
}: {
  items: Array<{ field: string; accuracy: number }>
}) {
  return (
    <Stack spacing={1.5} role="img" aria-label="Exact-match accuracy by field">
      {items.map((item) => {
        const pct = Math.round(item.accuracy * 1000) / 10
        return (
          <Box key={item.field}>
            <Stack direction="row" justifyContent="space-between" mb={0.5}>
              <Typography variant="body2" fontWeight={600} sx={{ textTransform: 'capitalize' }}>
                {item.field.replace(/_/g, ' ')}
              </Typography>
              <Typography variant="body2" fontWeight={700} color="primary.main">
                {pct.toFixed(1)}%
              </Typography>
            </Stack>
            <Box sx={{ position: 'relative', height: 14, bgcolor: '#E8EEF5', borderRadius: 7 }}>
              <Box
                sx={{
                  height: 14,
                  width: `${Math.max(pct, pct > 0 ? 2 : 0)}%`,
                  borderRadius: 7,
                  background: 'linear-gradient(90deg, #1976d2, #42a5f5)',
                }}
              />
            </Box>
          </Box>
        )
      })}
    </Stack>
  )
}

/**
 * Entity Precision / Recall / F1: Original OCR vs pharmacist-accepted values.
 * Uses normalized equivalence (case / spacing / synonyms). Clinical SIG changes
 * (capsule≠tablet, 3×≠4×, 1≠2 tablets) still count as misses. Indication excluded.
 */
function fieldValuesEquivalent(
  field: string,
  ocrRaw: string,
  acceptedRaw: string,
  row: Record<string, string | boolean | null>,
): boolean {
  const ocr = ocrRaw.trim()
  const accepted = acceptedRaw.trim()
  if (!ocr || !accepted) return false
  if (ocr === accepted) return true
  // Prefer backend normalized flag when present (cached analytics after recompute)
  if (row.normalized_match === true) return true
  if (row.normalized_match === false) return false
  // Client fallback for older cached payloads
  const a = ocr.toLowerCase().replace(/\s+/g, ' ').trim()
  const b = accepted.toLowerCase().replace(/\s+/g, ' ').trim()
  if (a === b) return true
  if (field === 'strength') {
    const normStrength = (s: string) =>
      s
        .replace(/(\d+(?:\.\d+)?)\s*\/\s*1\b/g, '$1')
        .replace(/(\d+(?:\.\d+)?)(mg|mcg|g|ml|%)\b/g, '$1 $2')
        .replace(/\s+/g, ' ')
        .trim()
    return normStrength(a) === normStrength(b)
  }
  return false
}

function EntityOcrPrfCharts({
  comparisonRows,
}: {
  comparisonRows: Array<Record<string, string | boolean | null>>
}) {
  const fmtRate = (v: number | null | undefined) =>
    v == null ? '—' : `${(v * 100).toFixed(1)}%`

  const fieldOrder = ['drug_name', 'strength', 'dosage', 'frequency', 'route', 'duration']

  const { ocrScores, mismatches } = useMemo(() => {
    const pairs = comparisonRows.filter(
      (r) => r.field !== 'indication' && r.ocr_scorable !== false,
    )
    const entities = fieldOrder.filter((f) => pairs.some((r) => r.field === f))

    const ocr = entities.map((entity) => {
      const rows = pairs.filter((r) => r.field === entity)
      let tp = 0
      let fp = 0
      let fn = 0
      for (const r of rows) {
        const ocrV = String(r.ocr_value ?? '').trim()
        const accepted = String(r.confirmed_value ?? '').trim()
        const matched = fieldValuesEquivalent(entity, ocrV, accepted, r)
        if (ocrV && accepted && matched) tp += 1
        else if (ocrV && (!accepted || !matched)) {
          fp += 1
          if (accepted && !matched) fn += 1
        } else if (accepted && !ocrV) fn += 1
      }
      const precision = tp + fp === 0 ? null : tp / (tp + fp)
      const recall = tp + fn === 0 ? null : tp / (tp + fn)
      const f1 =
        precision == null || recall == null
          ? null
          : precision + recall === 0
            ? 0
            : (2 * precision * recall) / (precision + recall)
      return {
        entity,
        precision: precision == null ? null : Math.round(precision * 10000) / 10000,
        recall: recall == null ? null : Math.round(recall * 10000) / 10000,
        f1: f1 == null ? null : Math.round(f1 * 10000) / 10000,
        true_positives: tp,
        false_positives: fp,
        false_negatives: fn,
      }
    })

    const miss = pairs
      .filter((r) => {
        const ocrV = String(r.ocr_value ?? '').trim()
        const accepted = String(r.confirmed_value ?? '').trim()
        if (!accepted || !ocrV) return Boolean(accepted) && !ocrV
        return !fieldValuesEquivalent(String(r.field), ocrV, accepted, r)
      })
      .map((r) => ({
        medicine: String(r.medicine),
        field: String(r.field),
        ocr: r.ocr_value == null || r.ocr_value === '' ? '—' : String(r.ocr_value),
        accepted: String(r.confirmed_value),
      }))

    return { ocrScores: ocr, mismatches: miss }
  }, [comparisonRows])

  const accent = '#1565c0'
  const chartH = 180
  const ticks = [0, 25, 50, 75, 100]
  const metrics = [
    { key: 'precision' as const, label: 'Precision', color: '#0d47a1' },
    { key: 'recall' as const, label: 'Recall', color: '#1565c0' },
    { key: 'f1' as const, label: 'F1', color: '#42a5f5' },
  ]

  return (
    <Stack spacing={2}>
      <Alert severity="info" sx={{ py: 0.75 }}>
        <strong>OCR vs pharmacist-accepted (normalized):</strong> case and spacing do not lower
        F1 (e.g. <em>Ibuprofen</em>/<em>ibuprofen</em>, <em>400mg</em>/<em>400 mg</em>). Clinical
        changes do: <em>ONE capsule</em> ≠ <em>ONE tablet</em>, <em>THREE times daily</em> ≠{' '}
        <em>FOUR times daily</em>, <em>ONE tablet</em> ≠ <em>TWO tablets</em>. Indication is
        excluded (no OCR baseline).
      </Alert>

      {mismatches.length > 0 && (
        <Box sx={{ border: 1, borderColor: 'warning.light', borderRadius: 2, p: 1.5, bgcolor: '#FFF8E1' }}>
          <Typography variant="subtitle2" fontWeight={800} gutterBottom>
            OCR ≠ pharmacist-accepted (these lower P/R/F1)
          </Typography>
          <Stack spacing={0.75}>
            {mismatches.map((m, i) => (
              <Typography key={i} variant="body2" sx={{ fontFamily: 'ui-monospace, Consolas, monospace' }}>
                <strong>{m.medicine}</strong> · {m.field.replace(/_/g, ' ')}: OCR “{m.ocr}” ≠ accepted “
                {m.accepted}”
              </Typography>
            ))}
          </Stack>
        </Box>
      )}

      <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap>
        {metrics.map((m) => (
          <Stack key={m.key} direction="row" spacing={0.5} alignItems="center">
            <Box sx={{ width: 12, height: 12, bgcolor: m.color, borderRadius: 0.5 }} />
            <Typography variant="caption" fontWeight={700}>
              {m.label}
            </Typography>
          </Stack>
        ))}
      </Stack>

      <Box sx={{ display: 'flex', gap: 1, minHeight: chartH + 48 }}>
        <Box sx={{ width: 36, position: 'relative', height: chartH, flexShrink: 0 }}>
          {ticks.map((t) => (
            <Typography
              key={t}
              variant="caption"
              color="text.secondary"
              sx={{
                position: 'absolute',
                right: 4,
                top: `${100 - t}%`,
                transform: 'translateY(-50%)',
                lineHeight: 1,
              }}
            >
              {t}
            </Typography>
          ))}
        </Box>
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Box
            sx={{
              position: 'relative',
              height: chartH,
              borderLeft: '1px solid',
              borderBottom: '1px solid',
              borderColor: 'divider',
              bgcolor: '#fff',
              display: 'flex',
              alignItems: 'stretch',
              px: 0.5,
              gap: 0.75,
            }}
          >
            {ticks.slice(1).map((t) => (
              <Box
                key={t}
                sx={{
                  position: 'absolute',
                  left: 0,
                  right: 0,
                  bottom: `${t}%`,
                  borderTop: '1px dashed',
                  borderColor: 'rgba(0,0,0,0.07)',
                  pointerEvents: 'none',
                }}
              />
            ))}
            {ocrScores.map((row) => (
              <Box
                key={row.entity}
                sx={{
                  flex: 1,
                  minWidth: 0,
                  display: 'flex',
                  alignItems: 'flex-end',
                  justifyContent: 'center',
                  gap: '3px',
                  position: 'relative',
                  zIndex: 1,
                  bgcolor: 'rgba(21,101,192,0.05)',
                  borderRadius: '6px 6px 0 0',
                  px: 0.4,
                }}
              >
                {metrics.map((m) => {
                  const val = row[m.key]
                  const pct = val == null ? 0 : Math.max(0, Math.min(100, val * 100))
                  return (
                    <Box
                      key={m.key}
                      title={`${row.entity.replace(/_/g, ' ')} ${m.label}: ${fmtRate(val)}`}
                      sx={{
                        width: '28%',
                        maxWidth: 26,
                        height: `${pct}%`,
                        minHeight: val == null || pct === 0 ? 2 : undefined,
                        bgcolor: m.color,
                        borderRadius: '3px 3px 0 0',
                        opacity: val == null ? 0.25 : 1,
                      }}
                    />
                  )
                })}
              </Box>
            ))}
          </Box>
          <Box sx={{ display: 'flex', gap: 0.75, px: 0.5, mt: 0.75 }}>
            {ocrScores.map((row) => (
              <Typography
                key={row.entity}
                variant="caption"
                fontWeight={700}
                sx={{
                  flex: 1,
                  textAlign: 'center',
                  textTransform: 'capitalize',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                  color: accent,
                }}
                title={row.entity.replace(/_/g, ' ')}
              >
                {row.entity.replace(/_/g, ' ')}
              </Typography>
            ))}
          </Box>
        </Box>
      </Box>

      <TableContainer sx={{ border: 1, borderColor: 'divider', borderRadius: 2 }}>
        <Table size="small" sx={tableSx}>
          <TableHead>
            <TableRow>
              <TableCell>Entity</TableCell>
              <TableCell align="right">Matched</TableCell>
              <TableCell align="right">Not matched</TableCell>
              <TableCell align="right">Precision</TableCell>
              <TableCell align="right">Recall</TableCell>
              <TableCell align="right">F1</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {ocrScores.map((row) => (
              <TableRow key={row.entity}>
                <TableCell sx={{ textTransform: 'capitalize', fontWeight: 700 }}>
                  {row.entity.replace(/_/g, ' ')}
                </TableCell>
                <TableCell align="right">{row.true_positives}</TableCell>
                <TableCell align="right">
                  {row.false_positives + row.false_negatives === 0
                    ? 0
                    : `FP ${row.false_positives} / FN ${row.false_negatives}`}
                </TableCell>
                <TableCell align="right">{fmtRate(row.precision)}</TableCell>
                <TableCell align="right">{fmtRate(row.recall)}</TableCell>
                <TableCell align="right" sx={{ fontWeight: 800, color: accent }}>
                  {fmtRate(row.f1)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Stack>
  )
}

/** Diverging accept/reject bars for every confirmed medicine */
function AlternativesByMedicineChart({
  rows,
}: {
  rows: Array<Record<string, string | number | null>>
}) {
  if (!rows.length) {
    return (
      <Typography variant="body2" color="text.secondary">
        No confirmed medicines yet.
      </Typography>
    )
  }
  const maxSide = Math.max(
    1,
    ...rows.map((r) => Math.max(Number(r.accepted || 0), Number(r.rejected || 0))),
  )
  return (
    <Stack spacing={2} role="img" aria-label="Alternatives decisions by confirmed medicine">
      {rows.map((row, idx) => {
        const accepted = Number(row.accepted || 0)
        const rejected = Number(row.rejected || 0)
        const leftPct = (accepted / maxSide) * 50
        const rightPct = (rejected / maxSide) * 50
        return (
          <Box
            key={idx}
            sx={{
              p: 1.5,
              borderRadius: 2,
              bgcolor: '#fff',
              border: '1px solid',
              borderColor: 'divider',
            }}
          >
            <Typography variant="body2" fontWeight={700} mb={1}>
              {String(row.prescribed_medicine)}
            </Typography>
            <Box sx={{ display: 'flex', alignItems: 'center', height: 28, gap: 0 }}>
              <Typography variant="caption" sx={{ width: 28, textAlign: 'right', color: '#2e7d32', fontWeight: 700 }}>
                {accepted}
              </Typography>
              <Box sx={{ flex: 1, display: 'flex', height: 18, mx: 1 }}>
                <Box sx={{ flex: 1, display: 'flex', justifyContent: 'flex-end', bgcolor: '#E8F5E9', borderRadius: '9px 0 0 9px' }}>
                  <Box
                    sx={{
                      width: `${leftPct * 2}%`,
                      bgcolor: '#2e7d32',
                      borderRadius: '9px 0 0 9px',
                      minWidth: accepted > 0 ? 6 : 0,
                    }}
                    title={`Accepted ${accepted}`}
                  />
                </Box>
                <Box sx={{ width: 2, bgcolor: '#90A4AE' }} />
                <Box sx={{ flex: 1, display: 'flex', justifyContent: 'flex-start', bgcolor: '#FFEBEE', borderRadius: '0 9px 9px 0' }}>
                  <Box
                    sx={{
                      width: `${rightPct * 2}%`,
                      bgcolor: '#c62828',
                      borderRadius: '0 9px 9px 0',
                      minWidth: rejected > 0 ? 6 : 0,
                    }}
                    title={`Rejected ${rejected}`}
                  />
                </Box>
              </Box>
              <Typography variant="caption" sx={{ width: 28, color: '#c62828', fontWeight: 700 }}>
                {rejected}
              </Typography>
            </Box>
            <Stack direction="row" justifyContent="space-between" mt={0.5}>
              <Typography variant="caption" color="#2e7d32">
                Accepted
              </Typography>
              <Typography variant="caption" color="#c62828">
                Rejected
              </Typography>
            </Stack>
            {accepted + rejected === 0 && (
              <Typography variant="caption" color="text.secondary">
                No Accept / Reject decisions yet for this medicine
              </Typography>
            )}
          </Box>
        )
      })}
    </Stack>
  )
}

const tableSx = {
  '& th': {
    bgcolor: '#F5F7FA',
    fontWeight: 700,
    whiteSpace: 'nowrap',
    borderBottom: '2px solid',
    borderColor: 'divider',
  },
  '& td': { py: 1.1 },
  '& tbody tr:nth-of-type(even)': { bgcolor: '#FAFBFC' },
  '& tbody tr:hover': { bgcolor: '#EEF5FF' },
}

export function SummaryAnalyticsPanel({
  sessionId,
  refreshToken,
}: {
  sessionId: string
  refreshToken?: string | number
}) {
  const [data, setData] = useState<AnalyticsPayload | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [updatedAt, setUpdatedAt] = useState<string | null>(null)

  const load = useCallback(async () => {
    setBusy(true)
    setError('')
    try {
      const { data: payload } = await api.get<AnalyticsPayload>(
        `/api/v1/prescriptions/${sessionId}/analytics`,
        { params: { refresh: true } },
      )
      setData(payload)
      setUpdatedAt(new Date().toLocaleTimeString())
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(typeof detail === 'string' ? detail : 'Could not load summary analytics.')
    } finally {
      setBusy(false)
    }
  }, [sessionId])

  useEffect(() => {
    void load()
  }, [load, refreshToken])

  const download = async (format: 'json' | 'csv', table: string) => {
    const res = await api.get(`/api/v1/prescriptions/${sessionId}/analytics/export`, {
      params: { format, table },
      responseType: 'blob',
    })
    const url = URL.createObjectURL(res.data)
    const a = document.createElement('a')
    a.href = url
    a.download = `${table}.${format}`
    a.click()
    URL.revokeObjectURL(url)
  }

  if (!data) {
    return (
      <Stack spacing={1}>
        <Typography variant="h6">Summary Analytics</Typography>
        {busy ? <Typography color="text.secondary">Loading analytics…</Typography> : null}
        {error && <Alert severity="error">{error}</Alert>}
      </Stack>
    )
  }

  if (!data.available) {
    return (
      <Stack spacing={1}>
        <Typography variant="h6">Summary Analytics</Typography>
        <Alert severity="info">
          {data.message ||
            'Analytics will appear after the prescription pipeline is completed and at least one medicine is confirmed.'}
        </Alert>
      </Stack>
    )
  }

  const s = data.summary || {}
  const alt = (data.alternative_metrics || {}) as Record<string, unknown>
  const accepted = Number(
    s.pharmacist_accepted_alternatives ?? s.alternative_accepted ?? alt.accepted_for_further_review ?? 0,
  )
  const rejected = Number(
    s.pharmacist_rejected_alternatives ?? s.alternative_rejected ?? alt.rejected ?? 0,
  )
  const perMedAlt = (alt.per_medicine as Array<Record<string, string | number | null>>) || []

  return (
    <Stack spacing={2.5} sx={{ width: '100%' }}>
      <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
        <Typography variant="h6">Summary Analytics</Typography>
        <Chip
          size="small"
          color={
            (data.demo_label || '').includes('DEMO') || (data.provenance_label || '').includes('DEMO')
              ? 'warning'
              : 'success'
          }
          variant={
            (data.demo_label || '').includes('DEMO') ? 'filled' : 'outlined'
          }
          label={data.provenance_label || data.demo_label || 'Session metrics'}
        />
        {updatedAt && (
          <Typography variant="caption" color="text.secondary">
            Updated {updatedAt}
          </Typography>
        )}
        <Button size="small" disabled={busy} onClick={() => void load()}>
          {busy ? 'Refreshing…' : 'Refresh'}
        </Button>
      </Stack>
      <Alert severity="info">{data.disclaimer}</Alert>

      <Typography variant="subtitle1" fontWeight={700}>
        KPI overview
      </Typography>
      <Box
        sx={{
          display: 'grid',
          gap: 1.25,
          gridTemplateColumns: {
            xs: 'repeat(2, minmax(0, 1fr))',
            sm: 'repeat(4, minmax(0, 1fr))',
            md: 'repeat(7, minmax(0, 1fr))',
          },
          width: '100%',
        }}
      >
        <KpiCard label="Items detected" value={fmtNum(s.prescription_items_detected as number)} accent="#455a64" />
        <KpiCard label="Medicines confirmed" value={fmtNum(s.medicines_confirmed as number)} accent="#2e7d32" />
        <KpiCard label="Total fields" value={fmtNum(s.total_fields_evaluated as number)} accent="#1565c0" />
        <KpiCard label="Fields corrected" value={fmtNum(s.fields_corrected as number)} accent="#ef6c00" />
        <KpiCard
          label="Avg OCR confidence"
          value={
            s.average_ocr_confidence == null
              ? 'N/A'
              : `${((s.average_ocr_confidence as number) * 100).toFixed(1)}%`
          }
          accent="#00838f"
        />
        <KpiCard
          label="TA accepted (pharmacist)"
          value={fmtNum(accepted)}
          accent="#2e7d32"
        />
        <KpiCard
          label="TA rejected (pharmacist)"
          value={fmtNum(rejected)}
          accent="#c62828"
        />
      </Box>
      <Typography variant="caption" color="text.secondary">
        Usability KPIs: OCR field agreement vs pharmacist-accepted values (indication excluded). TA
        accepted/rejected = pharmacist decisions on suggested alternatives — not automatic substitution.
      </Typography>

      <Box
        sx={{
          display: 'grid',
          gap: 2,
          gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' },
        }}
      >
        <Box sx={{ border: 1, borderColor: 'divider', borderRadius: 2, p: 2, bgcolor: '#FAFBFC' }}>
          <Typography variant="subtitle2" fontWeight={700} gutterBottom>
            Exact-match accuracy by field
          </Typography>
          <Typography variant="caption" color="text.secondary" display="block" mb={1.5}>
            Original OCR vs pharmacist-accepted (exact string; indication excluded)
          </Typography>
          <ExactMatchChart
            items={(data.field_metrics || []).map((f) => ({
              field: String(f.field),
              accuracy: Number(f.exact_match_accuracy || 0),
            }))}
          />
        </Box>

        <Box sx={{ border: 1, borderColor: 'divider', borderRadius: 2, p: 2, bgcolor: '#FAFBFC', maxHeight: 520, overflow: 'auto' }}>
          <Typography variant="subtitle2" fontWeight={700} gutterBottom>
            Alternatives by prescribed medicine
          </Typography>
          <Typography variant="caption" color="text.secondary" display="block" mb={1.5}>
            Diverging Accept (left) vs Reject (right) for every confirmed medicine
          </Typography>
          <AlternativesByMedicineChart rows={perMedAlt} />
        </Box>
      </Box>

      <Box sx={{ border: 1, borderColor: 'divider', borderRadius: 2, p: 2, bgcolor: '#FAFBFC' }}>
        <Typography variant="subtitle1" fontWeight={800} gutterBottom>
          Entity Precision / Recall / F1 (OCR vs pharmacist-accepted)
        </Typography>
        <EntityOcrPrfCharts comparisonRows={data.comparison_rows || []} />
      </Box>

      <Box sx={{ border: 1, borderColor: 'divider', borderRadius: 2, p: 2 }}>
        <Typography variant="subtitle2" fontWeight={700} gutterBottom>
          CER / WER (final pipeline)
        </Typography>
        <Stack spacing={1} maxWidth={480}>
          <Box>
            <Stack direction="row" justifyContent="space-between">
              <Typography variant="body2">CER</Typography>
              <Typography variant="body2" fontWeight={700}>
                {data.text_metrics?.full_prescription?.final_cer == null
                  ? 'Not available'
                  : `${Number(data.text_metrics.full_prescription.final_cer).toFixed(2)}%`}
              </Typography>
            </Stack>
            <LinearProgress
              variant="determinate"
              value={Math.min(100, Number(data.text_metrics?.full_prescription?.final_cer ?? 0))}
              sx={{ height: 8, borderRadius: 4, mt: 0.5 }}
            />
          </Box>
          <Box>
            <Stack direction="row" justifyContent="space-between">
              <Typography variant="body2">WER</Typography>
              <Typography variant="body2" fontWeight={700}>
                {data.text_metrics?.full_prescription?.final_wer == null
                  ? 'Not available'
                  : `${Number(data.text_metrics.full_prescription.final_wer).toFixed(2)}%`}
              </Typography>
            </Stack>
            <LinearProgress
              variant="determinate"
              value={Math.min(100, Number(data.text_metrics?.full_prescription?.final_wer ?? 0))}
              color="secondary"
              sx={{ height: 8, borderRadius: 4, mt: 0.5 }}
            />
          </Box>
        </Stack>
        <Typography variant="caption" color="text.secondary" display="block" mt={1}>
          Lower is better. Hypothesis = Original OCR · Reference = pharmacist-accepted instruction text.
        </Typography>
      </Box>

      <Typography variant="subtitle2" fontWeight={700}>
        Medicine-level performance
      </Typography>
      <TableContainer sx={{ border: 1, borderColor: 'divider', borderRadius: 2 }}>
        <Table size="small" sx={tableSx}>
          <TableHead>
            <TableRow>
              <TableCell>Medicine</TableCell>
              <TableCell>OCR conf.</TableCell>
              <TableCell>Drug match</TableCell>
              <TableCell>Fields</TableCell>
              <TableCell>Exact</TableCell>
              <TableCell>Normalized</TableCell>
              <TableCell>Corrected</TableCell>
              <TableCell>CER</TableCell>
              <TableCell>WER</TableCell>
              <TableCell>Entity F1</TableCell>
              <TableCell>BertScore F1</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {(data.medicine_performance || []).map((m) => (
              <TableRow key={String(m.medicine_name)}>
                <TableCell>
                  <Typography variant="body2" fontWeight={700}>
                    {String(m.medicine_name)}
                  </Typography>
                </TableCell>
                <TableCell>
                  {m.ocr_confidence == null ? (
                    'Not available'
                  ) : (
                    <Chip
                      size="small"
                      label={`${(Number(m.ocr_confidence) * 100).toFixed(1)}%`}
                      color={Number(m.ocr_confidence) >= 0.8 ? 'success' : 'warning'}
                      sx={{ height: 22, fontWeight: 600 }}
                    />
                  )}
                </TableCell>
                <TableCell>
                  <Chip size="small" variant="outlined" label={String(m.drug_match_result)} sx={{ height: 22 }} />
                </TableCell>
                <TableCell>{fmtNum(m.fields_evaluated as number)}</TableCell>
                <TableCell>{fmtNum(m.exact_fields as number)}</TableCell>
                <TableCell>{fmtNum(m.normalized_fields as number)}</TableCell>
                <TableCell>{fmtNum(m.corrected_fields as number)}</TableCell>
                <TableCell>{m.cer == null ? 'Not available' : Number(m.cer).toFixed(4)}</TableCell>
                <TableCell>{m.wer == null ? 'Not available' : Number(m.wer).toFixed(4)}</TableCell>
                <TableCell>{m.entity_f1 == null ? 'Not available' : Number(m.entity_f1).toFixed(4)}</TableCell>
                <TableCell>
                  {m.bertscore_f1 == null || m.bertscore_f1 === 'Not calculated'
                    ? 'Not calculated'
                    : Number(m.bertscore_f1).toFixed(4)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
        <Button size="small" variant="outlined" onClick={() => void download('json', 'all')}>
          Export JSON
        </Button>
        <Button size="small" variant="outlined" onClick={() => void download('csv', 'field_comparison')}>
          Export field comparison CSV
        </Button>
        <Button size="small" variant="outlined" onClick={() => void download('csv', 'medicine_performance')}>
          Export medicine performance CSV
        </Button>
      </Stack>
      {error && <Alert severity="error">{error}</Alert>}
    </Stack>
  )
}
