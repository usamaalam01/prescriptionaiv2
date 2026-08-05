import { Button, Chip, Stack, Typography } from '@mui/material'
import { Link as RouterLink } from 'react-router-dom'
import type { User } from '../types'

function homeMessage(role: User['role']): string {
  if (role === 'administrator') {
    return 'Administrator home — open the Administrator portal for dashboard, registrations, catalog, prescriptions, and analytics.'
  }
  if (role === 'pharmacist') {
    return 'Pharmacist home — analyze prescriptions with HITL, or explore the FDA NDC / DrugBank / SPL catalog used for verification.'
  }
  return 'Reviewer home — open the evaluation snapshot for aggregate research metrics (no patient identifiers).'
}

export function HomePage({ user, onLogout }: { user: User; onLogout: () => void }) {
  return (
    <Stack spacing={2} sx={{ bgcolor: 'background.paper', border: 1, borderColor: 'divider', borderRadius: 2, p: 3 }}>
      <Typography variant="h4">Welcome, {user.username}</Typography>
      <Chip label={user.role} color="primary" sx={{ width: 'fit-content' }} />
      <Typography color="text.secondary">{homeMessage(user.role)}</Typography>
      {user.role === 'pharmacist' && (
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1}>
          <Button component={RouterLink} to="/analyzer" variant="contained" sx={{ width: 'fit-content' }}>
            Prescription Analyzer
          </Button>
          <Button component={RouterLink} to="/catalog" variant="outlined" sx={{ width: 'fit-content' }}>
            Medicine catalog explorer
          </Button>
        </Stack>
      )}
      {user.role === 'reviewer' && (
        <Button component={RouterLink} to="/research/evaluation" variant="contained" sx={{ width: 'fit-content' }}>
          Evaluation snapshot
        </Button>
      )}
      {user.must_change_password && (
        <Typography color="warning.main">
          A password change is required — you will be redirected to set a new password.
        </Typography>
      )}
      <Button variant="outlined" onClick={onLogout} sx={{ width: 'fit-content' }}>
        Logout
      </Button>
    </Stack>
  )
}
