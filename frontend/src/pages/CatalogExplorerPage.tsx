import { useEffect, useMemo, useState } from 'react'
import {
  Alert,
  Box,
  Button,
  Chip,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import { Link as RouterLink } from 'react-router-dom'
import { api } from '../api'

interface CatalogSource {
  id: string
  label: string
  role: string
  rows_ingested?: number | null
}

interface Overview {
  available: boolean
  built_at?: string
  disclaimer: string
  intended_use: string
  sources: CatalogSource[]
  unified: {
    medicines?: number
    aliases?: number
    full_data?: boolean
    build_seconds?: number
  }
}

interface IndicationOpt {
  value: string
  sources?: string[]
}

interface LookupSelected {
  canonical_name: string
  score: number
  source: string
  strengths: string[]
  dosage_forms: string[]
  routes: string[]
  drugbank_id?: string | null
  product_ndc?: string | null
  matched_alias?: string | null
  reason?: string
  brand_names?: string[]
  indication_options?: IndicationOpt[]
  indication_snippet?: string | null
  sources_list?: string[]
  aliases_sample?: string[]
}

interface LookupResponse {
  query: string
  candidates: LookupSelected[]
  selected: LookupSelected | null
  disclaimer: string
  note?: string
}

function sourceChipColor(src: string): 'default' | 'primary' | 'secondary' | 'success' | 'warning' {
  const u = src.toUpperCase()
  if (u.includes('DRUGBANK')) return 'primary'
  if (u.includes('SPL')) return 'success'
  if (u.includes('NDC')) return 'warning'
  return 'default'
}

export function CatalogExplorerPage({ onLogout }: { onLogout?: () => void }) {
  const [overview, setOverview] = useState<Overview | null>(null)
  const [query, setQuery] = useState('Cetirizine')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<LookupResponse | null>(null)

  useEffect(() => {
    void api
      .get<Overview>('/api/v1/catalog/overview')
      .then((r) => setOverview(r.data))
      .catch(() => setOverview(null))
  }, [])

  const search = async (q?: string) => {
    const term = (q ?? query).trim()
    if (term.length < 2) return
    setBusy(true)
    setError('')
    try {
      const { data } = await api.get<LookupResponse>('/api/v1/catalog/lookup', {
        params: { q: term, top_k: 8 },
      })
      setResult(data)
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(typeof detail === 'string' ? detail : 'Catalog lookup failed.')
      setResult(null)
    } finally {
      setBusy(false)
    }
  }

  const selected = result?.selected
  const statsLine = useMemo(() => {
    if (!overview?.unified) return null
    const u = overview.unified
    return `${u.medicines?.toLocaleString?.() ?? u.medicines ?? '—'} medicines · ${
      u.aliases?.toLocaleString?.() ?? u.aliases ?? '—'
    } aliases`
  }, [overview])

  return (
    <Stack spacing={2.5} sx={{ width: '100%', maxWidth: 1100, mx: 'auto' }}>
      <Stack
        direction={{ xs: 'column', sm: 'row' }}
        justifyContent="space-between"
        alignItems={{ sm: 'flex-start' }}
        spacing={1}
      >
        <Stack spacing={1}>
          <Typography
            variant="overline"
            sx={{ letterSpacing: '0.14em', color: 'text.secondary', fontFamily: 'Georgia, serif' }}
          >
            Dataset intelligence
          </Typography>
          <Typography variant="h4" sx={{ fontFamily: 'Georgia, "Times New Roman", serif', fontWeight: 600 }}>
            Medicine catalog explorer
          </Typography>
          <Typography color="text.secondary" maxWidth={720}>
            Browse the unified local catalog built from FDA NDC, DrugBank, and FDA SPL. Use this to verify
            strengths and indication evidence before HITL confirmation in the Analyzer.
          </Typography>
        </Stack>
        {onLogout && (
          <Button variant="outlined" size="small" onClick={() => void onLogout()}>
            Logout
          </Button>
        )}
      </Stack>

      <Alert severity="warning">{overview?.intended_use || 'Decision-support only — not clinical care.'}</Alert>

      {overview && (
        <Box
          sx={{
            border: 1,
            borderColor: 'divider',
            borderRadius: 2,
            p: 2.5,
            background:
              'linear-gradient(165deg, rgba(15, 61, 46, 0.06) 0%, rgba(255,255,255,1) 45%, rgba(120, 53, 15, 0.05) 100%)',
          }}
        >
          <Stack spacing={1.5}>
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap alignItems="center">
              <Chip
                size="small"
                color={overview.available ? 'success' : 'warning'}
                label={overview.available ? 'Catalog ready' : 'Catalog missing'}
              />
              {statsLine && <Typography variant="body2">{statsLine}</Typography>}
              {overview.built_at && (
                <Typography variant="caption" color="text.secondary">
                  Built {overview.built_at}
                </Typography>
              )}
            </Stack>
            <Stack direction={{ xs: 'column', md: 'row' }} spacing={2}>
              {overview.sources.map((s) => (
                <Box key={s.id} sx={{ flex: 1, minWidth: 0 }}>
                  <Typography variant="subtitle2">{s.label}</Typography>
                  <Typography variant="body2" color="text.secondary">
                    {s.role}
                  </Typography>
                  <Typography variant="h6" sx={{ mt: 0.5, fontFamily: 'Georgia, serif' }}>
                    {s.rows_ingested != null ? s.rows_ingested.toLocaleString() : '—'}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    rows ingested
                  </Typography>
                </Box>
              ))}
            </Stack>
          </Stack>
        </Box>
      )}

      <Box sx={{ border: 1, borderColor: 'divider', borderRadius: 2, p: 2 }}>
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} alignItems={{ sm: 'flex-start' }}>
          <TextField
            fullWidth
            size="small"
            label="Search verified medicines"
            placeholder="e.g. Augmentin, Cetirizine, Pantoprazole"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') void search()
            }}
          />
          <Button variant="contained" disabled={busy || query.trim().length < 2} onClick={() => void search()}>
            Lookup
          </Button>
          <Button component={RouterLink} to="/analyzer" variant="outlined">
            Open Analyzer
          </Button>
        </Stack>
        <Stack direction="row" spacing={1} sx={{ mt: 1.5 }} flexWrap="wrap" useFlexGap>
          {['Amoxicillin', 'Ibuprofen', 'Cetirizine', 'Pantoprazole', 'Augmentin'].map((example) => (
            <Chip
              key={example}
              label={example}
              size="small"
              onClick={() => {
                setQuery(example)
                void search(example)
              }}
              variant="outlined"
            />
          ))}
        </Stack>
      </Box>

      {error && <Alert severity="error">{error}</Alert>}

      {selected && (
        <Box sx={{ border: 1, borderColor: 'divider', borderRadius: 2, p: 2.5 }}>
          <Stack spacing={1.5}>
            <Typography variant="h5" sx={{ fontFamily: 'Georgia, serif' }}>
              {selected.canonical_name}
            </Typography>
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
              {(selected.sources_list || selected.source.split('+')).map((s) => (
                <Chip key={s} size="small" color={sourceChipColor(s)} label={s} />
              ))}
              {selected.drugbank_id && <Chip size="small" variant="outlined" label={selected.drugbank_id} />}
              {selected.product_ndc && (
                <Chip size="small" variant="outlined" label={`NDC ${selected.product_ndc}`} />
              )}
              <Chip size="small" variant="outlined" label={`${Math.round(selected.score)}% match`} />
            </Stack>
            <Typography variant="body2" color="text.secondary">
              {selected.reason}
              {selected.matched_alias ? ` · matched alias “${selected.matched_alias}”` : ''}
            </Typography>

            <Typography variant="subtitle2">Strengths (dataset)</Typography>
            <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap>
              {(selected.strengths || []).slice(0, 16).map((s) => (
                <Chip key={s} size="small" label={s} variant="outlined" />
              ))}
              {!selected.strengths?.length && (
                <Typography variant="body2" color="text.secondary">
                  No strength rows on this catalog entry — try a related generic (e.g. amoxicillin and
                  clavulanate potassium for Augmentin).
                </Typography>
              )}
            </Stack>

            <Typography variant="subtitle2">Forms / routes</Typography>
            <Typography variant="body2">
              {(selected.dosage_forms || []).slice(0, 8).join(' · ') || '—'}
              {(selected.routes || []).length ? ` · Routes: ${selected.routes.slice(0, 6).join(', ')}` : ''}
            </Typography>

            <Typography variant="subtitle2">Indication evidence (dataset-derived, optional in HITL)</Typography>
            {selected.indication_snippet && (
              <Typography variant="body2" color="text.secondary">
                {selected.indication_snippet}
                {selected.indication_snippet.length >= 270 ? '…' : ''}
              </Typography>
            )}
            <Stack spacing={0.75}>
              {(selected.indication_options || []).slice(0, 8).map((opt) => (
                <Box key={opt.value}>
                  <Typography variant="body2">{opt.value}</Typography>
                  <Typography variant="caption" color="text.secondary">
                    {(opt.sources || []).join(' · ')}
                  </Typography>
                </Box>
              ))}
              {!selected.indication_options?.length && (
                <Typography variant="body2" color="text.secondary">
                  No short indication labels extracted for this entry.
                </Typography>
              )}
            </Stack>
          </Stack>
        </Box>
      )}

      {result && result.candidates.length > 1 && (
        <Box sx={{ border: 1, borderColor: 'divider', borderRadius: 2, p: 2 }}>
          <Typography variant="subtitle2" gutterBottom>
            Similar catalog candidates (pharmacist must confirm)
          </Typography>
          <Stack spacing={1}>
            {result.candidates.map((c) => (
              <Stack
                key={`${c.canonical_name}-${c.score}`}
                direction={{ xs: 'column', sm: 'row' }}
                justifyContent="space-between"
                spacing={0.5}
              >
                <Typography variant="body2">{c.canonical_name}</Typography>
                <Typography variant="caption" color="text.secondary">
                  {c.source} · {Math.round(c.score)}%
                </Typography>
              </Stack>
            ))}
          </Stack>
        </Box>
      )}

      {overview?.disclaimer && (
        <Typography variant="caption" color="text.secondary">
          {overview.disclaimer}
        </Typography>
      )}
    </Stack>
  )
}
