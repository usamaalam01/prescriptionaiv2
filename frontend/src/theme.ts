import { createTheme } from '@mui/material/styles'

export const theme = createTheme({
  palette: {
    primary: { main: '#003366', contrastText: '#ffffff' },
    secondary: { main: '#6B3FA0' },
    success: { main: '#1B7F4B' },
    warning: { main: '#A85F00' },
    error: { main: '#B3261E' },
    background: { default: '#F5F7FA', paper: '#FFFFFF' },
  },
  shape: { borderRadius: 12 },
  typography: {
    fontFamily: '"IBM Plex Sans", "Segoe UI", sans-serif',
    h1: { fontFamily: '"Source Serif 4", Georgia, serif', fontWeight: 700 },
    h2: { fontFamily: '"Source Serif 4", Georgia, serif', fontWeight: 700 },
    h3: { fontFamily: '"Source Serif 4", Georgia, serif', fontWeight: 700 },
    h4: { fontFamily: '"Source Serif 4", Georgia, serif', fontWeight: 600 },
    h5: { fontFamily: '"Source Serif 4", Georgia, serif', fontWeight: 600 },
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: { textTransform: 'none', fontWeight: 700 },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: { boxShadow: '0 2px 12px rgba(0, 51, 102, 0.08)' },
      },
    },
  },
})
