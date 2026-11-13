import apiClient from './client';

export async function minePatterns(jobId, minSupport = 0.1, maxPatternLength = 3) {
  const response = await apiClient.post('/mine-patterns', {
    job_id: jobId,
    min_support: minSupport,
    max_pattern_length: maxPatternLength,
  });
  return response.data;
}

export async function getPatterns(jobId) {
  const response = await apiClient.get('/mine-patterns', {
    params: { job_id: jobId },
  });
  return response.data;
}
