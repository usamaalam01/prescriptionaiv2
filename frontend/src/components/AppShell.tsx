import type { ReactNode } from 'react'
import { Box, Typography } from '@mui/material'

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <Box minHeight="100vh" display="flex" flexDirection="column" sx={{ overflowX: 'hidden' }}>
      <Box sx={{ bgcolor: 'primary.main', color: 'primary.contrastText', px: { xs: 2, md: 4 }, py: 2 }}>
        <Typography variant="h5" component="div">
          MediScan
        </Typography>
        <Typography variant="body2" sx={{ opacity: 0.9 }}>
          Human-in-the-Loop, Explainable AI Decision-Support for Prescription Reading &amp; Therapeutically-Equivalent
          Medicine Substitution · NED University of Engineering &amp; Technology
        </Typography>
      </Box>

      <Box sx={{ bgcolor: '#EAF2FA', px: { xs: 2, md: 4 }, py: 1 }}>
        <Typography variant="caption">
          PGD in Generative AI · Academic research prototype
        </Typography>
      </Box>

      <Box sx={{ bgcolor: '#FFF4E5', color: '#5F370E', px: { xs: 2, md: 4 }, py: 1.25, textAlign: 'center' }}>
        <Typography variant="body2">
          <strong>Clinical disclaimer:</strong> Decision-support only. All outputs must be reviewed and
          confirmed by a qualified pharmacist. Not for actual patient treatment.
        </Typography>
      </Box>

      <Box
        component="main"
        sx={{
          flex: 1,
          width: '100%',
          maxWidth: 1400,
          mx: 'auto',
          px: { xs: 2, sm: 3, md: 4 },
          py: { xs: 2.5, md: 3.5 },
          boxSizing: 'border-box',
        }}
      >
        {children}
      </Box>

      <Box sx={{ bgcolor: '#003366', color: '#fff', textAlign: 'center', py: 2, px: 2 }}>
        <Typography variant="caption" display="block">
          Prototype developed for academic research as part of Post Graduate Diploma in Generative AI at NED
          University of Engineering &amp; Technology
        </Typography>
        <Typography variant="caption" display="block">
          Student: Muhammad Usama Alam · Supervisor: Sajid Majeed
        </Typography>
      </Box>
    </Box>
  )
}
