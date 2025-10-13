import React from 'react';
import { 
  Box, 
  Typography, 
  Button, 
  Paper, 
  Alert,
  Container
} from '@mui/material';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    // Update state so the next render will show the fallback UI
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    // Log the error to console for debugging
    console.error('Error Boundary caught an error:', error, errorInfo);
    
    this.setState({
      error: error,
      errorInfo: errorInfo
    });
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        <Container maxWidth="md" sx={{ mt: 4 }}>
          <Paper sx={{ p: 4, textAlign: 'center' }}>
            <Typography variant="h4" color="error" gutterBottom>
              🚨 Something went wrong
            </Typography>
            
            <Typography variant="h6" gutterBottom sx={{ mb: 3 }}>
              The application encountered an unexpected error
            </Typography>
            
            <Alert severity="error" sx={{ mb: 3, textAlign: 'left' }}>
              <Typography variant="body2">
                <strong>Error:</strong> {this.state.error && this.state.error.toString()}
              </Typography>
            </Alert>
            
            <Box sx={{ display: 'flex', gap: 2, justifyContent: 'center', mb: 3 }}>
              <Button 
                variant="contained" 
                color="primary" 
                onClick={this.handleReset}
                size="large"
              >
                🔄 Try Again
              </Button>
              <Button 
                variant="outlined" 
                onClick={() => window.location.reload()}
                size="large"
              >
                🔃 Reload Page
              </Button>
            </Box>
            
            <Typography variant="body2" color="text.secondary">
              If the problem persists, please check the browser console for more details or contact support.
            </Typography>
            
            {process.env.NODE_ENV === 'development' && this.state.errorInfo && (
              <Box sx={{ mt: 3, textAlign: 'left' }}>
                <Typography variant="h6" gutterBottom>
                  Development Error Details:
                </Typography>
                <Box 
                  component="pre" 
                  sx={{ 
                    backgroundColor: '#f5f5f5', 
                    p: 2, 
                    borderRadius: 1, 
                    overflow: 'auto',
                    fontSize: '0.8rem',
                    maxHeight: '300px'
                  }}
                >
                  {this.state.errorInfo.componentStack}
                </Box>
              </Box>
            )}
          </Paper>
        </Container>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
