import apiClient from './client';

export async function analyzeDataset(jobId) {
  const response = await apiClient.post('/analyze', {
    job_id: jobId,
  });
  return response.data;
}

export async function getAnalytics(jobId) {
  const response = await apiClient.get('/analyze', {
    params: { job_id: jobId },
  });
  return response.data;
}
