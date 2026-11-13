import apiClient from './client';

export async function generateInsights(jobId) {
  const response = await apiClient.post('/insights', {
    job_id: jobId,
  });
  return response.data;
}

export async function getInsights(jobId) {
  const response = await apiClient.get('/insights', {
    params: { job_id: jobId },
  });
  return response.data;
}
