import apiClient from './client';

export async function getColumnMapping(jobId) {
  const response = await apiClient.get('/map-columns', {
    params: { job_id: jobId },
  });
  return response.data;
}

export async function mapColumns(jobId, mapping) {
  const response = await apiClient.post('/map-columns', {
    job_id: jobId,
    mapping,
  });
  return response.data;
}

export async function getValueMapping(jobId) {
  const response = await apiClient.get('/map-values', {
    params: { job_id: jobId },
  });
  return response.data;
}

export async function mapValues(jobId, mapping) {
  const response = await apiClient.post('/map-values', {
    job_id: jobId,
    mapping,
  });
  return response.data;
}
