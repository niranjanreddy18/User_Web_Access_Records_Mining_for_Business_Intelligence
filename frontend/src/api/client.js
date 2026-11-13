import axios from 'axios';

const baseURL = import.meta.env.VITE_API_BASE_URL || '/api';

const apiClient = axios.create({
  baseURL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export function extractApiError(error, fallback = 'An unexpected error occurred. Please try again.') {
  const data = error?.response?.data;
  if (data && typeof data === 'object') {
    if (typeof data.error === 'string' && data.error.trim()) {
      return data.error;
    }
    if (typeof data.detail === 'string' && data.detail.trim()) {
      return data.detail;
    }
  }
  if (error?.message && !error.message.includes('status code')) {
    return error.message;
  }
  return fallback;
}

export default apiClient;
