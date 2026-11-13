import { Navigate } from 'react-router-dom';
import { useJob } from '../../hooks/useJob';

export default function ProtectedRoute({ stepKey, children }) {
  const { jobId, canAccessStep } = useJob();

  if (!jobId) {
    return <Navigate to="/upload" replace />;
  }

  if (stepKey && !canAccessStep(stepKey)) {
    return <Navigate to="/upload" replace />;
  }

  return children;
}
