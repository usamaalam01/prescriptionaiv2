import { Fragment, useMemo, useState } from 'react'
import {
  Alert,
  Box,
  Chip,
  Collapse,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material'

export interface OcrCandidate {
  text?: string
  engine?: string
  confidence?: number
}

export interface OcrMergedLine {
  line_id?: string
  selected_text?: string
  selected_engine?: string
  selected_confidence?: number
  conflict?: boolean
  used_trocr_retry?: boolean
  candidates?: OcrCandidate[]
}

export interface OcrPipelineMeta {
  merged_lines?: OcrMergedLine[]
  warnings?: string[]
  stages_used?: string[]
  processing_ms?: number
  overall_ocr_confidence?: number
}

const LOW_CONF = 0.78

type LineFilter = 'all' | 'attention' | 'conflict'

function pct(n: number | undefined) {
  if (n == null || Number.isNaN(n)) return '—'
  return `${(n * 100).toFixed(0)}%`
}

function confColor(n: number | undefined): 'success' | 'warning' | 'error' | 'default' {
  if (n == null) return 'default'
  if (n >= 0.9) return 'success'
  if (n >= LOW_CONF) return 'warning'
  return 'error'
}

/**
 * Pillar-1 OCR explainability: per-line confidence, engine, conflicts, candidates.
 * Pharmacist resolves ambiguous drug/SIG values in HITL — this panel shows why OCR was uncertain.
 */
export function OcrConflictPanel({
  pipeline,
  overallConfidence,
  isMock,
}: {
  pipeline?: OcrPipelineMeta | null
  overallConfidence?: number
  isMock?: boolean
}) {
  const [filter, setFilter] = useState<LineFilter>('attention')
  const [expandedId, setExpandedId] = useState<string | null>(null)

  const lines = pipeline?.merged_lines || []
  const warnings = pipeline?.warnings || []

  const stats = useMemo(() => {
    const conflict = lines.filter((l) => l.conflict).length
    const low = lines.filter((l) => (l.selected_confidence ?? 1) < LOW_CONF).length
    const retry = lines.filter((l) => l.used_trocr_retry).length
    const engines = new Set(
      lines.map((l) => l.selected_engine).filter(Boolean) as string[],
    )
    return { total: lines.length, conflict, low, retry, engines: [...engines] }
  }, [lines])

  const visible = useMemo(() => {
    if (filter === 'conflict') return lines.filter((l) => l.conflict)
    if (filter === 'attention') {
      return lines.filter(
        (l) => l.conflict || (l.selected_confidence ?? 1) < LOW_CONF || l.used_trocr_retry,
      )
    }
    return lines
  }, [lines, filter])

  if (!pipeline && overallConfidence == null) return null

  return (
    <Stack spacing={1.25} sx={{ mt: 0.5 }}>
      <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap alignItems="center">
        <Typography variant="subtitle2">OCR line confidence</Typography>
        {overallConfidence != null && (
          <Chip
            size="small"
            color={confColor(overallConfidence)}
            label={`Overall ${pct(overallConfidence)}`}
          />
        )}
        <Chip size="small" variant="outlined" label={`${stats.total} lines`} />
        {stats.conflict > 0 && (
          <Chip size="small" color="warning" label={`${stats.conflict} conflict`} />
        )}
        {stats.low > 0 && (
          <Chip size="small" color="error" variant="outlined" label={`${stats.low} low conf`} />
        )}
        {stats.retry > 0 && (
          <Chip size="small" variant="outlined" label={`${stats.retry} crop retry`} />
        )}
        {stats.engines.map((e) => (
          <Chip key={e} size="small" variant="outlined" label={e} />
        ))}
        {isMock && <Chip size="small" color="warning" label="MOCK" />}
      </Stack>

      <Typography variant="caption" color="text.secondary">
        Lines below {Math.round(LOW_CONF * 100)}% or with engine disagreement need HITL attention.
        Selected text feeds the medical parser; Confirm only after catalog match.
      </Typography>

      {lines.length > 0 && (
        <>
          <ToggleButtonGroup
            exclusive
            size="small"
            value={filter}
            onChange={(_e, v: LineFilter | null) => {
              if (v) setFilter(v)
            }}
          >
            <ToggleButton value="attention">Needs attention</ToggleButton>
            <ToggleButton value="conflict">Conflicts</ToggleButton>
            <ToggleButton value="all">All lines</ToggleButton>
          </ToggleButtonGroup>

          {visible.length === 0 ? (
            <Alert severity="success" sx={{ py: 0.5 }}>
              No conflicting or low-confidence lines for this filter.
            </Alert>
          ) : (
            <Box
              sx={{
                border: 1,
                borderColor: 'divider',
                borderRadius: 1,
                maxHeight: 280,
                overflow: 'auto',
              }}
            >
              <Table size="small" stickyHeader>
                <TableHead>
                  <TableRow>
                    <TableCell sx={{ fontWeight: 700, width: 72 }}>Conf</TableCell>
                    <TableCell sx={{ fontWeight: 700 }}>Selected text</TableCell>
                    <TableCell sx={{ fontWeight: 700, width: 100 }}>Engine</TableCell>
                    <TableCell sx={{ fontWeight: 700, width: 88 }}>Flags</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {visible.map((line, idx) => {
                    const id = line.line_id || `line-${idx}`
                    const open = expandedId === id
                    const conf = line.selected_confidence
                    const hasCandidates = (line.candidates?.length || 0) > 1
                    return (
                      <Fragment key={id}>
                        <TableRow
                          hover
                          onClick={() => setExpandedId(open ? null : id)}
                          sx={{
                            cursor: hasCandidates || line.conflict ? 'pointer' : 'default',
                            bgcolor:
                              (conf ?? 1) < LOW_CONF
                                ? 'error.50'
                                : line.conflict
                                  ? 'warning.50'
                                  : undefined,
                          }}
                        >
                          <TableCell>
                            <Chip size="small" color={confColor(conf)} label={pct(conf)} />
                          </TableCell>
                          <TableCell>
                            <Typography
                              variant="body2"
                              sx={{ fontFamily: 'ui-monospace, monospace', fontSize: 12 }}
                            >
                              {line.selected_text || '—'}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Typography variant="caption">{line.selected_engine || '—'}</Typography>
                          </TableCell>
                          <TableCell>
                            <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
                              {line.conflict && (
                                <Chip size="small" color="warning" label="conflict" />
                              )}
                              {line.used_trocr_retry && (
                                <Chip size="small" variant="outlined" label="retry" />
                              )}
                            </Stack>
                          </TableCell>
                        </TableRow>
                        <TableRow>
                          <TableCell colSpan={4} sx={{ py: 0, border: 0 }}>
                            <Collapse in={open} timeout="auto" unmountOnExit>
                              <Box sx={{ px: 1.5, py: 1, bgcolor: 'grey.50' }}>
                                <Typography variant="caption" color="text.secondary" display="block">
                                  Candidates (highest confidence was selected automatically)
                                </Typography>
                                <Stack spacing={0.5} sx={{ mt: 0.5 }}>
                                  {(line.candidates || []).map((c, i) => (
                                    <Stack
                                      key={`${id}-c-${i}`}
                                      direction="row"
                                      spacing={1}
                                      alignItems="center"
                                    >
                                      <Chip
                                        size="small"
                                        color={confColor(c.confidence)}
                                        label={pct(c.confidence)}
                                        sx={{ minWidth: 52 }}
                                      />
                                      <Typography variant="caption" sx={{ minWidth: 72 }}>
                                        {c.engine || '—'}
                                      </Typography>
                                      <Typography
                                        variant="caption"
                                        sx={{ fontFamily: 'ui-monospace, monospace' }}
                                      >
                                        {c.text || '—'}
                                      </Typography>
                                      {c.text === line.selected_text &&
                                        c.engine === line.selected_engine && (
                                          <Chip size="small" color="success" label="selected" />
                                        )}
                                    </Stack>
                                  ))}
                                  {!line.candidates?.length && (
                                    <Typography variant="caption" color="text.secondary">
                                      No alternate candidates stored for this line.
                                    </Typography>
                                  )}
                                </Stack>
                              </Box>
                            </Collapse>
                          </TableCell>
                        </TableRow>
                      </Fragment>
                    )
                  })}
                </TableBody>
              </Table>
            </Box>
          )}
        </>
      )}

      {lines.length === 0 && (
        <Typography variant="caption" color="text.secondary">
          No per-line OCR metadata on this job (raw transcript only).
        </Typography>
      )}

      {warnings.length > 0 && (
        <Alert severity="info" sx={{ py: 0.5 }}>
          <Typography variant="caption" component="div">
            Pipeline notes ({warnings.length}): {warnings.slice(0, 3).join(' · ')}
            {warnings.length > 3 ? '…' : ''}
          </Typography>
        </Alert>
      )}
    </Stack>
  )
}
