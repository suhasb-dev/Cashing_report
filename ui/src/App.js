import React, { useState } from 'react';
import { 
  Container, 
  Paper, 
  TextField, 
  Button, 
  Typography, 
  Box,
  LinearProgress,
  Alert,
  Tabs,
  Tab,
  Grid,
  Card,
  CardContent,
  Chip,
  Divider
} from '@mui/material';
import JsonView from '@uiw/react-json-view';
import axios from 'axios';
import ErrorBoundary from './ErrorBoundary';
import './App.css';

// Configure axios with longer timeout for bulk operations
axios.defaults.timeout = 300000; // 5 minutes timeout

// Tab Panel Component
function TabPanel({ children, value, index, ...other }) {
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`simple-tabpanel-${index}`}
      aria-labelledby={`simple-tab-${index}`}
      {...other}
    >
      {value === index && (
        <Box sx={{ p: 3 }}>
          {children}
        </Box>
      )}
    </div>
  );
}

function App() {
  const [tabValue, setTabValue] = useState(0);
  const [formData, setFormData] = useState({
    command: '',
    packageName: '',
    startDate: '',
    endDate: ''
  });
  const [jsonData, setJsonData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [loadingMessage, setLoadingMessage] = useState('');
  const [error, setError] = useState(null);
  const [bulkAnalysisData, setBulkAnalysisData] = useState(null);
  const [analyses, setAnalyses] = useState([]);
  const [selectedAnalysis, setSelectedAnalysis] = useState(null);
  const [selectedReport, setSelectedReport] = useState(null);
  const [reportContent, setReportContent] = useState(null);
  const [expandedAnalyses, setExpandedAnalyses] = useState({});
  const [reportSearchQuery, setReportSearchQuery] = useState('');

  const handleTabChange = (event, newValue) => {
    setTabValue(newValue);
  };

  const handleInputChange = (field) => (event) => {
    setFormData({
      ...formData,
      [field]: event.target.value
    });
  };

  const handleCommandAnalysis = async () => {
    setLoading(true);
    setLoadingMessage('Analyzing command...');
    setError(null);
    try {
      const response = await axios.post('/api/v1/analyze-command', formData);
      setJsonData(response.data);
    } catch (err) {
      console.error('Command analysis error:', err);
      if (err.code === 'ECONNABORTED') {
        setError('Request timed out. Please try again.');
      } else if (err.response?.status === 500) {
        setError(`Server error: ${err.response?.data?.error || 'Internal server error'}`);
      } else if (err.response?.status === 404) {
        setError(`No data found: ${err.response?.data?.error || 'Command not found'}`);
      } else {
        setError(err.response?.data?.message || err.message || 'Failed to analyze command');
      }
    } finally {
      setLoading(false);
      setLoadingMessage('');
    }
  };

  const handleBulkAnalysis = async () => {
    setLoading(true);
    setLoadingMessage('Running bulk analysis... This may take several minutes.');
    setError(null);
    try {
      const response = await axios.post('/api/v1/bulk-analyze', {
        startDate: formData.startDate,
        endDate: formData.endDate
      });
      setBulkAnalysisData(response.data);
    } catch (err) {
      console.error('Bulk analysis error:', err);
      if (err.code === 'ECONNABORTED') {
        setError('Request timed out. Bulk analysis is taking longer than expected. Please try again.');
      } else if (err.response?.status === 500) {
        setError(`Server error: ${err.response?.data?.error || 'Internal server error'}`);
      } else {
        setError(err.response?.data?.message || err.message || 'Failed to run bulk analysis');
      }
    } finally {
      setLoading(false);
      setLoadingMessage('');
    }
  };

  const handleClearResults = () => {
    setJsonData(null);
    setBulkAnalysisData(null);
    setError(null);
    setSelectedReport(null);
    setReportContent(null);
  };

  const fetchAnalyses = async () => {
    try {
      setLoading(true);
      setLoadingMessage('Loading analyses...');
      const response = await axios.get('/api/v1/reports');
      setAnalyses(response.data.analyses || []);
      
      // Auto-expand the latest analysis
      if (response.data.analyses?.length > 0) {
        const latestAnalysisId = response.data.analyses[0].id;
        setExpandedAnalyses(prev => ({
          ...prev,
          [latestAnalysisId]: true
        }));
      }
    } catch (err) {
      console.error('Error fetching analyses:', err);
      setError('Failed to load analyses. Please try again.');
    } finally {
      setLoading(false);
      setLoadingMessage('');
    }
  };

  const toggleAnalysis = (analysisId) => {
    setExpandedAnalyses(prev => ({
      ...prev,
      [analysisId]: !prev[analysisId]
    }));
  };

  const handleReportSelect = async (analysisDir, report) => {
    try {
      setLoading(true);
      setLoadingMessage('Loading report...');
      setSelectedAnalysis(analysisDir);
      setSelectedReport(report);
      
      // Construct the correct path: analysis_<timestamp>/filename.json
      const reportPath = report.path || `${analysisDir}/${report.filename}`;
      const response = await axios.get(`/api/v1/reports/${reportPath}`);
      setReportContent(response.data);
    } catch (err) {
      console.error('Error loading report:', err);
      setError('Failed to load report. Please try again.');
    } finally {
      setLoading(false);
      setLoadingMessage('');
    }
  };

  // Load analyses when the Reports tab is selected
  React.useEffect(() => {
    if (tabValue === 2) { // Reports tab is selected
      fetchAnalyses();
    }
  }, [tabValue]);

  // Format date for display
  const formatDate = (timestamp) => {
    if (!timestamp) return 'N/A';
    const date = new Date(timestamp);
    return date.toLocaleString();
  };

  // Format file size
  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  return (
    <ErrorBoundary>
      <Container maxWidth="xl" sx={{ mt: 2, mb: 4 }}>
        {/* Header */}
        <Paper sx={{ p: 3, mb: 3, background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)', color: 'white' }}>
          <Typography variant="h3" component="h1" gutterBottom align="center">
            🚀 Cache Failure Classification System
          </Typography>
          <Typography variant="h6" align="center" sx={{ opacity: 0.9 }}>
            Intelligent cache failure analysis and reporting for DynamoDB-based test automation
          </Typography>
        </Paper>

      {/* Main Content */}
      <Paper sx={{ p: 2 }}>
        <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Tabs value={tabValue} onChange={handleTabChange} aria-label="analysis tabs">
            <Tab label="Command Analysis" />
            <Tab label="Bulk Analysis" />
            <Tab label="Reports" />
            <Tab label="System Overview" />
          </Tabs>
        </Box>

        {/* Command Analysis Tab */}
        <TabPanel value={tabValue} index={0}>
          <ErrorBoundary>
            <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    📊 Command Analysis
                  </Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                    Analyze cache performance for a specific command and package combination
                  </Typography>
                  
                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                    <TextField
                      label="Command"
                      value={formData.command}
                      onChange={handleInputChange('command')}
                      fullWidth
                      placeholder="e.g., Tap on Submit Button"
                      helperText="Enter the exact command text from your test steps"
                    />
                    <TextField
                      label="Package Name"
                      value={formData.packageName}
                      onChange={handleInputChange('packageName')}
                      fullWidth
                      placeholder="e.g., in.swiggy.android.instamart"
                      helperText="Enter the app package name"
                    />
                    <TextField
                      label="Start Date"
                      type="date"
                      value={formData.startDate}
                      onChange={handleInputChange('startDate')}
                      InputLabelProps={{ shrink: true }}
                      helperText="Analysis start date (IST timezone)"
                    />
                    <TextField
                      label="End Date"
                      type="date"
                      value={formData.endDate}
                      onChange={handleInputChange('endDate')}
                      InputLabelProps={{ shrink: true }}
                      helperText="Analysis end date (IST timezone)"
                    />
                    
                    <Box sx={{ display: 'flex', gap: 2, mt: 2 }}>
                      <Button 
                        variant="contained" 
                        onClick={handleCommandAnalysis}
                        disabled={loading || !formData.command || !formData.packageName}
                        size="large"
                      >
                        🔍 Analyze Command
                      </Button>
                      <Button 
                        variant="outlined" 
                        onClick={handleClearResults}
                        disabled={loading}
                      >
                        Clear Results
                      </Button>
                    </Box>
                  </Box>
                </CardContent>
              </Card>
            </Grid>

            <Grid item xs={12} md={6}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    📈 Analysis Results
                  </Typography>
                  
                  {loading && (
                    <Box sx={{ mb: 2 }}>
                      <LinearProgress />
                      {loadingMessage && (
                        <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                          {loadingMessage}
                        </Typography>
                      )}
                    </Box>
                  )}
                  
                  {error && (
                    <Alert severity="error" sx={{ mb: 2 }}>
                      {error}
                    </Alert>
                  )}
                  
                  {jsonData ? (
                    <Box>
                      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                        Command: <strong>{jsonData.command}</strong><br/>
                        Package: <strong>{jsonData.app_package}</strong><br/>
                        Total Runs: <strong>{jsonData.total_step_runs}</strong>
                      </Typography>
                      <Divider sx={{ my: 2 }} />
                      <JsonView 
                        value={jsonData} 
                        style={{
                          backgroundColor: '#f5f5f5',
                          borderRadius: '8px',
                          padding: '16px'
                        }}
                        collapsed={false}
                        displayDataTypes={false}
                        displayObjectSize={false}
                      />
                    </Box>
                  ) : (
                    <Typography variant="body2" color="text.secondary">
                      Enter command details and click "Analyze Command" to see results
                    </Typography>
                  )}
                </CardContent>
              </Card>
            </Grid>
          </Grid>
          </ErrorBoundary>
        </TabPanel>

        {/* Bulk Analysis Tab */}
        <TabPanel value={tabValue} index={1}>
          <ErrorBoundary>
            <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    🔄 Bulk Analysis
                  </Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                    Run comprehensive analysis across all commands in your DynamoDB table
                  </Typography>
                  
                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                    <TextField
                      label="Start Date (Optional)"
                      type="date"
                      value={formData.startDate}
                      onChange={handleInputChange('startDate')}
                      InputLabelProps={{ shrink: true }}
                      helperText="Leave empty to analyze all data"
                    />
                    <TextField
                      label="End Date (Optional)"
                      type="date"
                      value={formData.endDate}
                      onChange={handleInputChange('endDate')}
                      InputLabelProps={{ shrink: true }}
                      helperText="Leave empty to analyze all data"
                    />
                    
                    <Box sx={{ display: 'flex', gap: 2, mt: 2 }}>
                      <Button 
                        variant="contained" 
                        onClick={handleBulkAnalysis}
                        disabled={loading}
                        size="large"
                        color="secondary"
                      >
                        🚀 Run Bulk Analysis
                      </Button>
                      <Button 
                        variant="outlined" 
                        onClick={handleClearResults}
                        disabled={loading}
                      >
                        Clear Results
                      </Button>
                    </Box>
                  </Box>
                </CardContent>
              </Card>
            </Grid>

            <Grid item xs={12} md={6}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    📊 Bulk Analysis Results
                  </Typography>
                  
                  {loading && (
                    <Box sx={{ mb: 2 }}>
                      <LinearProgress />
                      {loadingMessage && (
                        <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                          {loadingMessage}
                        </Typography>
                      )}
                    </Box>
                  )}
                  
                  {error && (
                    <Alert severity="error" sx={{ mb: 2 }}>
                      {error}
                    </Alert>
                  )}
                  
                  {bulkAnalysisData ? (
                    <Box>
                      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                        Analysis completed in <strong>{bulkAnalysisData.bulk_analysis_summary?.duration_seconds?.toFixed(2)}s</strong><br/>
                        Total steps processed: <strong>{bulkAnalysisData.bulk_analysis_summary?.total_steps_processed}</strong><br/>
                        Unique commands found: <strong>{bulkAnalysisData.bulk_analysis_summary?.unique_commands_found}</strong>
                      </Typography>
                      <Divider sx={{ my: 2 }} />
                      <JsonView 
                        value={bulkAnalysisData} 
                        style={{
                          backgroundColor: '#f5f5f5',
                          borderRadius: '8px',
                          padding: '16px'
                        }}
                        collapsed={false}
                        displayDataTypes={false}
                        displayObjectSize={false}
                      />
                    </Box>
                  ) : (
                    <Typography variant="body2" color="text.secondary">
                      Click "Run Bulk Analysis" to process all commands in your DynamoDB table
                    </Typography>
                  )}
                </CardContent>
              </Card>
            </Grid>
          </Grid>
          </ErrorBoundary>
        </TabPanel>

        {/* Reports Tab */}
        <TabPanel value={tabValue} index={2}>
          <ErrorBoundary>
            <Grid container spacing={3}>
              <Grid item xs={12} md={4}>
                <Card>
                  <CardContent>
                    <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                      <Typography variant="h6">
                        📋 Analysis Runs
                      </Typography>
                      <Button 
                        variant="outlined" 
                        size="small"
                        onClick={fetchAnalyses}
                        disabled={loading}
                      >
                        Refresh
                      </Button>
                    </Box>
                    
                    <TextField
                      fullWidth
                      size="small"
                      placeholder="Search reports by command or package..."
                      value={reportSearchQuery}
                      onChange={(e) => setReportSearchQuery(e.target.value)}
                      sx={{ mb: 2 }}
                    />
                    
                    {loading ? (
                      <Box sx={{ p: 2 }}>
                        <LinearProgress />
                        <Typography variant="body2" sx={{ mt: 1 }}>{loadingMessage}</Typography>
                      </Box>
                    ) : analyses.length === 0 ? (
                      <Typography variant="body2" color="text.secondary" sx={{ p: 2 }}>
                        No analysis runs found. Run a bulk analysis to generate reports.
                      </Typography>
                    ) : (
                      <Box sx={{ maxHeight: '70vh', overflow: 'auto' }}>
                        {analyses.map((analysis) => (
                          <Paper 
                            key={analysis.id}
                            sx={{
                              mb: 2,
                              borderLeft: 3,
                              borderColor: selectedAnalysis === analysis.directory ? 'primary.main' : 'divider'
                            }}
                          >
                            <Box 
                              onClick={() => toggleAnalysis(analysis.id)}
                              sx={{
                                p: 1.5,
                                cursor: 'pointer',
                                '&:hover': { bgcolor: 'action.hover' },
                                bgcolor: selectedAnalysis === analysis.directory ? 'action.selected' : 'background.paper',
                                display: 'flex',
                                justifyContent: 'space-between',
                                alignItems: 'center'
                              }}
                            >
                              <Box>
                                <Typography variant="subtitle2">
                                  {formatDate(analysis.start_time)}
                                </Typography>
                                <Typography variant="caption" color="text.secondary" display="block">
                                  {analysis.reports?.length || 0} reports • {analysis.status || 'unknown'}
                                </Typography>
                                {analysis.start_date && analysis.end_date && (
                                  <Typography variant="caption" color="text.secondary" display="block">
                                    Date range: {analysis.start_date} to {analysis.end_date}
                                  </Typography>
                                )}
                              </Box>
                              <Typography variant="h6">
                                {expandedAnalyses[analysis.id] ? '−' : '+'}
                              </Typography>
                            </Box>
                            
                            {expandedAnalyses[analysis.id] && analysis.reports?.length > 0 && (
                              <Box sx={{ p: 1, bgcolor: 'background.default' }}>
                                {analysis.reports
                                  .filter(report => {
                                    if (!reportSearchQuery) return true;
                                    const query = reportSearchQuery.toLowerCase();
                                    const searchIn = [
                                      report.command || '',
                                      report.app_package || '',
                                      report.filename || ''
                                    ].join(' ').toLowerCase();
                                    return searchIn.includes(query);
                                  })
                                  .map((report, index) => (
                                    <Paper 
                                      key={`${analysis.id}-${index}`}
                                      onClick={() => handleReportSelect(analysis.directory, report)}
                                      sx={{
                                        p: 1,
                                        mb: 0.5,
                                        cursor: 'pointer',
                                        '&:hover': { bgcolor: 'action.hover' },
                                        bgcolor: selectedReport?.filename === report.filename ? 'action.selected' : 'background.paper',
                                        borderLeft: 2,
                                        borderColor: selectedReport?.filename === report.filename ? 'primary.main' : 'divider'
                                      }}
                                    >
                                      <Typography variant="body2" noWrap>
                                        {report.command || report.filename}
                                      </Typography>
                                      <Typography variant="caption" color="text.secondary" display="block">
                                        {formatFileSize(report.size)}
                                      </Typography>
                                      {report.app_package && (
                                        <Typography variant="caption" color="text.secondary" noWrap>
                                          {report.app_package}
                                        </Typography>
                                      )}
                                    </Paper>
                                  ))}
                              </Box>
                            )}
                          </Paper>
                        ))}
                      </Box>
                    )}
                  </CardContent>
                </Card>
              </Grid>
              
              <Grid item xs={12} md={8}>
                <Card>
                  <CardContent>
                    <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                      <Box>
                        <Typography variant="h6">
                          {selectedReport ? selectedReport.command || selectedReport.filename : 'Select a report'}
                        </Typography>
                        {selectedReport && reportContent && (
                          <Box sx={{ mt: 1 }}>
                            {reportContent.data?.command && (
                              <Chip 
                                label={`Command: ${reportContent.data.command}`} 
                                size="small" 
                                sx={{ mr: 1, mb: 0.5 }} 
                              />
                            )}
                            {reportContent.data?.app_package && (
                              <Chip 
                                label={`Package: ${reportContent.data.app_package}`} 
                                size="small" 
                                color="primary" 
                                sx={{ mr: 1, mb: 0.5 }} 
                              />
                            )}
                            {reportContent.data?.total_step_runs && (
                              <Chip 
                                label={`Total Runs: ${reportContent.data.total_step_runs}`} 
                                size="small" 
                                color="success" 
                                sx={{ mb: 0.5 }} 
                              />
                            )}
                          </Box>
                        )}
                      </Box>
                      {selectedReport && (
                        <Box sx={{ textAlign: 'right' }}>
                          <Typography variant="caption" color="text.secondary" display="block">
                            {formatDate(selectedReport.modified)}
                          </Typography>
                          <Typography variant="caption" color="text.secondary" display="block">
                            {formatFileSize(reportContent?.size || selectedReport.size)}
                          </Typography>
                        </Box>
                      )}
                    </Box>
                    
                    {loading ? (
                      <Box sx={{ p: 2 }}>
                        <LinearProgress />
                        <Typography variant="body2" sx={{ mt: 1 }}>{loadingMessage}</Typography>
                      </Box>
                    ) : reportContent ? (
                      <Box sx={{
                        maxHeight: '70vh',
                        overflow: 'auto',
                        p: 1,
                        bgcolor: 'background.default',
                        borderRadius: 1
                      }}>
                        <JsonView 
                          value={reportContent.data} 
                          displayDataTypes={false}
                          displayObjectSize={false}
                          enableClipboard={true}
                          collapsed={1}
                          style={{
                            backgroundColor: 'transparent',
                            fontFamily: 'monospace',
                            fontSize: '0.875rem'
                          }}
                        />
                      </Box>
                    ) : (
                      <Typography variant="body2" color="text.secondary" sx={{ p: 2 }}>
                        Select a report from the list to view its contents
                      </Typography>
                    )}
                  </CardContent>
                </Card>
              </Grid>
            </Grid>
          </ErrorBoundary>
        </TabPanel>

        {/* System Overview Tab */}
        <TabPanel value={tabValue} index={3}>
          <ErrorBoundary>
            <Grid container spacing={3}>
            <Grid item xs={12}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    🏗️ System Architecture
                  </Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                    Understanding the Cache Failure Classification System
                  </Typography>
                  
                  <Grid container spacing={2}>
                    <Grid item xs={12} md={4}>
                      <Card variant="outlined">
                        <CardContent>
                          <Typography variant="h6" color="primary">
                            🎯 Priority-Based Classification
                          </Typography>
                          <Typography variant="body2" sx={{ mt: 1 }}>
                            Each step classified into exactly one category using 9-tier priority system
                          </Typography>
                        </CardContent>
                      </Card>
                    </Grid>
                    
                    <Grid item xs={12} md={4}>
                      <Card variant="outlined">
                        <CardContent>
                          <Typography variant="h6" color="primary">
                            🌏 IST Timezone Support
                          </Typography>
                          <Typography variant="body2" sx={{ mt: 1 }}>
                            Native Indian Standard Time (UTC+5:30) handling with automatic conversion
                          </Typography>
                        </CardContent>
                      </Card>
                    </Grid>
                    
                    <Grid item xs={12} md={4}>
                      <Card variant="outlined">
                        <CardContent>
                          <Typography variant="h6" color="primary">
                            📊 Comprehensive Analytics
                          </Typography>
                          <Typography variant="body2" sx={{ mt: 1 }}>
                            Detailed breakdown with percentages that sum to 100%
                          </Typography>
                        </CardContent>
                      </Card>
                    </Grid>
                  </Grid>
                  
                  <Divider sx={{ my: 3 }} />
                  
                  <Typography variant="h6" gutterBottom>
                    🔍 Classification Categories
                  </Typography>
                  
                  <Grid container spacing={1}>
                    {[
                      { name: 'Undoable', color: 'error' },
                      { name: 'Unblocker Call', color: 'warning' },
                      { name: 'OCR Steps', color: 'info' },
                      { name: 'Dynamic Step', color: 'secondary' },
                      { name: 'Failed Step', color: 'error' },
                      { name: 'Null LLM Output', color: 'warning' },
                      { name: 'Cache Read Status None', color: 'info' },
                      { name: 'No Cache Documents Found', color: 'default' },
                      { name: 'Less Similarity Threshold', color: 'default' },
                      { name: 'Failed At Must Match Filter', color: 'error' },
                      { name: 'Failed After Similar Document', color: 'warning' },
                      { name: 'Unclassified', color: 'default' }
                    ].map((category) => (
                      <Grid item key={category.name}>
                        <Chip 
                          label={category.name} 
                          color={category.color}
                          size="small"
                          variant="outlined"
                        />
                      </Grid>
                    ))}
                  </Grid>
                </CardContent>
              </Card>
            </Grid>
          </Grid>
          </ErrorBoundary>
        </TabPanel>
      </Paper>
      </Container>
    </ErrorBoundary>
  );
}

export default App;