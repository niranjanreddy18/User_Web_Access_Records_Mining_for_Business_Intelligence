import { createContext, useCallback, useContext, useState } from 'react';

const JobContext = createContext(null);

export const WORKFLOW_STEPS = [
  { key: 'upload', label: 'Upload CSV', path: '/upload', subtitle: 'Source data intake' },
  { key: 'mapping', label: 'Schema Mapping', path: '/mapping', subtitle: 'Columns & event values' },
  { key: 'quality', label: 'Data Quality', path: '/quality', subtitle: 'Validation & hygiene' },
  { key: 'dashboard', label: 'BI Dashboard', path: '/dashboard', subtitle: 'Metrics & distributions' },
  { key: 'patterns', label: 'Pattern Mining', path: '/patterns', subtitle: 'Journeys & transitions' },
  { key: 'insights', label: 'BI Insights', path: '/insights', subtitle: 'Deterministic observations' },
];

const STORAGE_KEY = 'wam_active_job_state';

const INITIAL_STATE = {
  jobId: null,
  filename: '',
  currentStep: 'upload',
  completedSteps: [],
  headers: [],
  columnMapping: {},
  valueMapping: {},
  qualityReport: null,
  analytics: null,
  patterns: null,
  insights: null,
};

function loadStoredState() {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (parsed && parsed.jobId) {
        return {
          ...INITIAL_STATE,
          ...parsed,
        };
      }
    }
  } catch {
    // Ignore storage parse errors
  }
  return INITIAL_STATE;
}

export function JobProvider({ children }) {
  const [jobState, setJobState] = useState(loadStoredState);

  const updateJob = useCallback((patch) => {
    setJobState((prev) => {
      const next = {
        ...prev,
        ...patch,
      };
      try {
        sessionStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      } catch {
        // Ignore storage errors
      }
      return next;
    });
  }, []);

  const completeStep = useCallback((stepKey, nextStepKey) => {
    setJobState((prev) => {
      const completed = prev.completedSteps.includes(stepKey)
        ? prev.completedSteps
        : [...prev.completedSteps, stepKey];
      const next = {
        ...prev,
        completedSteps: completed,
        currentStep: nextStepKey || prev.currentStep,
      };
      try {
        sessionStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      } catch {
        // Ignore storage errors
      }
      return next;
    });
  }, []);

  const resetJob = useCallback(() => {
    try {
      sessionStorage.removeItem(STORAGE_KEY);
    } catch {
      // Ignore
    }
    setJobState(INITIAL_STATE);
  }, []);

  const canAccessStep = useCallback(
    (stepKey) => {
      if (stepKey === 'upload') return true;
      if (!jobState.jobId) return false;
      if (stepKey === 'mapping') return jobState.completedSteps.includes('upload');
      if (stepKey === 'quality') return jobState.completedSteps.includes('mapping');
      if (stepKey === 'dashboard' || stepKey === 'patterns' || stepKey === 'insights') {
        return jobState.completedSteps.includes('quality');
      }
      return false;
    },
    [jobState.jobId, jobState.completedSteps]
  );

  return (
    <JobContext.Provider
      value={{
        ...jobState,
        updateJob,
        completeStep,
        resetJob,
        canAccessStep,
      }}
    >
      {children}
    </JobContext.Provider>
  );
}

export function useJob() {
  const context = useContext(JobContext);
  if (!context) {
    throw new Error('useJob must be used within a JobProvider.');
  }
  return context;
}
