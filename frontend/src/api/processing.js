import apiClient from './client';

export async function processDataset(jobId) {
  const response = await apiClient.post('/process', {
    job_id: jobId,
  });
  return response.data;
}

export async function getProcessingStatus(jobId) {
  const response = await apiClient.get('/process', {
    params: { job_id: jobId },
  });
  return response.data;
}

export async function sessionizeDataset(jobId, timeoutMinutes = 30) {
  const response = await apiClient.post('/sessionize', {
    job_id: jobId,
    timeout_minutes: timeoutMinutes,
  });
  return response.data;
}
