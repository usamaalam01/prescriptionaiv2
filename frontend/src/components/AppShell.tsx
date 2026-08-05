import type { ReactNode } from 'react'
import { Box, Typography } from '@mui/material'

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <Box minHeight="100vh" display="flex" flexDirection="column" sx={{ overflowX: 'hidden' }}>
      <Box sx={{ bgcolor: 'primary.main', color: 'primary.contrastText', px: { xs: 2, md: 4 }, py: 2 }}>
        <Typography variant="h5" component="div">
          PharmaAssist
        </Typography>
        <Typography variant="body2" sx={{ opacity: 0.9 }}>
          AI-Powered Pharma Assistant · University of Liverpool · CSCK700
        </Typography>
      </Box>

      <Box sx={{ bgcolor: '#EAF2FA', px: { xs: 2, md: 4 }, py: 1 }}>
        <Typography variant="caption">
          MSc Information Systems Management · Academic research prototype
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
        <Typography variant="caption">
          Prototype developed for academic research as part of the University of Liverpool CSCK700
          Computer Science Capstone Project.
        </Typography>
      </Box>
    </Box>
  )
}
