import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { SlidersHorizontal } from 'lucide-react';
import { extractApiError } from '../api/client';
import {
  getColumnMapping,
  getValueMapping,
  mapColumns,
  mapValues,
} from '../api/mapping';
import { processDataset } from '../api/processing';
import StatusBanner, { SkeletonCard } from '../components/layout/StatusBanner';
import ColumnMappingSection from '../components/mapping/ColumnMappingSection';
import ValueMappingSection from '../components/mapping/ValueMappingSection';
import { useJob } from '../hooks/useJob';

export default function Mapping() {
  const navigate = useNavigate();
  const {
    jobId,
    headers,
    columnMapping,
    valueMapping,
    updateJob,
    completeStep,
  } = useJob();

  const [localHeaders, setLocalHeaders] = useState(headers || []);
  const [localColumnMap, setLocalColumnMap] = useState(columnMapping || {});
  const [columnSaved, setColumnSaved] = useState(false);

  const [uniqueValues, setUniqueValues] = useState([]);
  const [unknownValues, setUnknownValues] = useState([]);
  const [allowedActions, setAllowedActions] = useState([]);
  const [localValueMap, setLocalValueMap] = useState(valueMapping || {});

  const [loadingColumns, setLoadingColumns] = useState(false);
  const [savingColumns, setSavingColumns] = useState(false);
  const [loadingValues, setLoadingValues] = useState(false);
  const [processingValues, setProcessingValues] = useState(false);
  const [error, setError] = useState('');
  const [statusMessage, setStatusMessage] = useState('');

  useEffect(() => {
    if (!jobId) return;
    if (localHeaders.length > 0) {
      // Auto-trigger value mapping lookup if columns already exist
      loadValueMappingDetails();
      return;
    }

    let active = true;
    setLoadingColumns(true);
    getColumnMapping(jobId)
      .then((data) => {
        if (!active) return;
        const detectedHeaders = data.headers || [];
        const initialMap =
          data.column_mapping && Object.keys(data.column_mapping).length > 0
            ? data.column_mapping
            : data.auto_mapping || {};
        setLocalHeaders(detectedHeaders);
        setLocalColumnMap(initialMap);
        updateJob({ headers: detectedHeaders, columnMapping: initialMap });
        // Inspect value mappings
        loadValueMappingDetails();
      })
      .catch((err) => {
        if (!active) return;
        setError(extractApiError(err, 'Failed to load column mapping schema.'));
      })
      .finally(() => {
        if (active) setLoadingColumns(false);
      });

    return () => {
      active = false;
    };
  }, [jobId]);

  const loadValueMappingDetails = async () => {
    setLoadingValues(true);
    setError('');
    try {
      const data = await getValueMapping(jobId);
      const unique = data.unique_values || [];
      const unknown = data.unknown_values || [];
      const allowed = data.allowed_actions || [];
      const autoMap = data.auto_mapping || {};
      const existing = data.value_mapping || {};

      const merged = { ...autoMap, ...existing };
      setUniqueValues(unique);
      setUnknownValues(unknown);
      setAllowedActions(allowed);
      setLocalValueMap(merged);
      updateJob({ valueMapping: merged });
      if (data.status === 'mapping' || Object.keys(existing).length > 0) {
        setColumnSaved(true);
      }
    } catch (err) {
      // If column mapping has not been submitted yet, it's expected
    } finally {
      setLoadingValues(false);
    }
  };

  const handleSaveColumns = async () => {
    if (savingColumns) return;
    setSavingColumns(true);
    setError('');
    setStatusMessage('');

    try {
      const data = await mapColumns(jobId, localColumnMap);
      const savedMapping = data.column_mapping || data.mapping || localColumnMap;
      updateJob({ columnMapping: savedMapping });
      setColumnSaved(true);
      setStatusMessage('Column mapping confirmed. Review detected action values below.');
      await loadValueMappingDetails();
    } catch (err) {
      setError(
        extractApiError(
          err,
          'Unable to save column mapping. Ensure all required fields are assigned unique columns.'
        )
      );
    } finally {
      setSavingColumns(false);
    }
  };

  const handleSaveValuesAndProcess = async () => {
    if (processingValues) return;
    setProcessingValues(true);
    setError('');
    setStatusMessage('');

    try {
      const valData = await mapValues(jobId, localValueMap);
      const savedValues = valData.value_mapping || valData.mapping || localValueMap;
      updateJob({ valueMapping: savedValues });

      const procData = await processDataset(jobId);
      updateJob({ qualityReport: procData.quality_report || {} });
      completeStep('mapping', 'quality');
      navigate('/quality');
    } catch (err) {
      setError(
        extractApiError(
          err,
          'Unable to process the dataset. Ensure all action values are mapped to a standard category.'
        )
      );
    } finally {
      setProcessingValues(false);
    }
  };

  return (
    <div className="mx-auto max-w-4xl space-y-8">
      <div className="border-b border-slate-200 pb-5">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-indigo-600">
          <SlidersHorizontal className="h-4 w-4" />
          Step 2: Schema &amp; Event Normalization
        </div>
        <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
          Schema &amp; Value Mapping
        </h1>
        <p className="mt-1.5 text-sm text-slate-600">
          Map heterogeneous column headers and standardize distinct event action values before
          running data validation.
        </p>
      </div>

      {loadingColumns && <StatusBanner type="loading" message="Loading detected CSV schema..." />}
      {loadingValues && <StatusBanner type="loading" message="Detecting unique event values..." />}
      {processingValues && (
        <StatusBanner
          type="loading"
          message="Validating, normalizing values, and executing data hygiene checks..."
        />
      )}
      {error && <StatusBanner type="error" message={error} onRetry={loadValueMappingDetails} />}
      {statusMessage && !error && <StatusBanner type="success" message={statusMessage} />}

      <ColumnMappingSection
        headers={localHeaders}
        mapping={localColumnMap}
        onChange={setLocalColumnMap}
        onSubmit={handleSaveColumns}
        loading={savingColumns || processingValues}
        submitted={columnSaved}
      />

      {columnSaved && !loadingValues && (
        <ValueMappingSection
          uniqueValues={uniqueValues}
          unknownValues={unknownValues}
          allowedActions={allowedActions}
          mapping={localValueMap}
          onChange={setLocalValueMap}
          onSubmit={handleSaveValuesAndProcess}
          loading={processingValues}
        />
      )}
    </div>
  );
}
