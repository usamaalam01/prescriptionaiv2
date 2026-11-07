import type { ReactNode } from 'react'
import { Avatar, Box, Stack, Typography } from '@mui/material'
import nedLogo from '../assets/ned-logo.jpg'

function AppIcon() {
  return (
    <Box
      component="svg"
      viewBox="0 0 48 48"
      sx={{ width: 44, height: 44, flexShrink: 0 }}
      aria-hidden="true"
    >
      <circle cx="24" cy="24" r="23" fill="#ffffff" fillOpacity={0.12} stroke="#ffffff" strokeOpacity={0.5} strokeWidth={1.5} />
      <rect x="14" y="10" width="20" height="26" rx="2.5" fill="#ffffff" />
      <rect x="17.5" y="14.5" width="13" height="2" rx="1" fill="#003366" />
      <rect x="17.5" y="18.5" width="13" height="2" rx="1" fill="#003366" opacity={0.75} />
      <rect x="17.5" y="22.5" width="9" height="2" rx="1" fill="#003366" opacity={0.55} />
      <circle cx="31.5" cy="30.5" r="7.5" fill="#1B9E6B" stroke="#ffffff" strokeWidth={1.5} />
      <path d="M31.5 27v7M28 30.5h7" stroke="#ffffff" strokeWidth={1.8} strokeLinecap="round" />
    </Box>
  )
}

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <Box minHeight="100vh" display="flex" flexDirection="column" sx={{ overflowX: 'hidden' }}>
      <Box
        sx={{
          bgcolor: 'primary.main',
          backgroundImage: 'linear-gradient(135deg, #003366 0%, #0A4A85 100%)',
          color: 'primary.contrastText',
          px: { xs: 2, md: 4 },
          py: { xs: 2, md: 2.5 },
        }}
      >
        <Stack
          direction="row"
          alignItems="center"
          justifyContent="space-between"
          spacing={{ xs: 1.5, md: 3 }}
          sx={{ maxWidth: 1400, mx: 'auto' }}
        >
          <Stack direction="row" alignItems="center" spacing={1.75}>
            <AppIcon />
            <Box>
              <Typography variant="h5" component="div" sx={{ fontWeight: 700, lineHeight: 1.15 }}>
                MediScan
              </Typography>
              <Typography variant="body2" sx={{ opacity: 0.88, maxWidth: 560, display: { xs: 'none', sm: 'block' } }}>
                Human-in-the-Loop, Explainable AI Decision-Support for Prescription Reading &amp;
                Therapeutically-Equivalent Medicine Substitution
              </Typography>
            </Box>
          </Stack>

          <Stack direction="row" alignItems="center" spacing={1.25} sx={{ flexShrink: 0 }}>
            <Box sx={{ textAlign: 'right', display: { xs: 'none', md: 'block' } }}>
              <Typography variant="caption" sx={{ opacity: 0.85, display: 'block', lineHeight: 1.3 }}>
                NED University of
              </Typography>
              <Typography variant="caption" sx={{ opacity: 0.85, display: 'block', lineHeight: 1.3 }}>
                Engineering &amp; Technology
              </Typography>
            </Box>
            <Avatar
              src={nedLogo}
              alt="NED University of Engineering & Technology"
              variant="circular"
              sx={{ width: 48, height: 48, bgcolor: '#ffffff', border: '2px solid rgba(255,255,255,0.6)' }}
            />
          </Stack>
        </Stack>
      </Box>

      <Box sx={{ bgcolor: '#EAF2FA', px: { xs: 2, md: 4 }, py: 1 }}>
        <Typography variant="caption" sx={{ color: '#003366', fontWeight: 600, letterSpacing: 0.3 }}>
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
