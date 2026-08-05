import { Component, type ErrorInfo, type ReactNode } from 'react'
import { Alert, Box, Button, Stack, Typography } from '@mui/material'

interface Props {
  children: ReactNode
}

interface State {
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('PharmaAssist UI error', error, info.componentStack)
  }

  private reset = () => {
    this.setState({ error: null })
  }

  render() {
    if (this.state.error) {
      return (
        <Box sx={{ maxWidth: 560, mx: 'auto', mt: 6, p: 2 }}>
          <Stack spacing={2}>
            <Typography variant="h5" sx={{ fontFamily: 'Georgia, serif' }}>
              Something went wrong
            </Typography>
            <Alert severity="error">
              The research UI hit an unexpected error. Your session data may still be safe — try
              reloading or returning home.
            </Alert>
            <Typography variant="body2" color="text.secondary">
              {this.state.error.message}
            </Typography>
            <Stack direction="row" spacing={1}>
              <Button variant="contained" onClick={this.reset}>
                Try again
              </Button>
              <Button variant="outlined" onClick={() => window.location.assign('/')}>
                Go home
              </Button>
            </Stack>
          </Stack>
        </Box>
      )
    }
    return this.props.children
  }
}
