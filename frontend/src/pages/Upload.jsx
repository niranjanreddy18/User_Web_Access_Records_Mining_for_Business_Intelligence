import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, FileCheck, ShieldAlert, Sparkles } from 'lucide-react';
import { extractApiError } from '../api/client';
import { uploadCsv } from '../api/upload';
import StatusBanner from '../components/layout/StatusBanner';
import CsvDropzone from '../components/upload/CsvDropzone';
import { useJob } from '../hooks/useJob';

export default function Upload() {
  const navigate = useNavigate();
  const { updateJob, resetJob } = useJob();

  const [selectedFile, setSelectedFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const handleFileSelect = (file) => {
    setError('');
    setSuccess('');
    if (!file.name.toLowerCase().endsWith('.csv')) {
      setError('Invalid file format. Please upload a valid .csv web access log file.');
      setSelectedFile(null);
      return;
    }
    if (file.size > 50 * 1024 * 1024) {
      setError('File size exceeds the 50 MB threshold. Please upload a smaller log excerpt.');
      setSelectedFile(null);
      return;
    }
    setSelectedFile(file);
  };

  const handleUpload = async () => {
    if (!selectedFile || loading) return;

    setLoading(true);
    setError('');
    setSuccess('');

    try {
      resetJob();
      const data = await uploadCsv(selectedFile);
      updateJob({
        jobId: data.job_id,
        filename: data.filename || selectedFile.name,
        headers: data.headers || [],
        columnMapping: data.auto_mapping || {},
        completedSteps: ['upload'],
        currentStep: 'mapping',
      });
      setSuccess('CSV uploaded and validated. Transitioning to schema mapping...');
      navigate('/mapping');
    } catch (err) {
      setError(
        extractApiError(
          err,
          'Unable to upload the CSV file. Please verify the server connection and file structure.'
        )
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-4xl space-y-8">
      {/* Page Header */}
      <div className="border-b border-slate-200 pb-5">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-indigo-600">
          <FileCheck className="h-4 w-4" />
          Step 1: Intake &amp; Ingestion
        </div>
        <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
          Upload Web Access CSV
        </h1>
        <p className="mt-1.5 text-sm text-slate-600">
          Upload server or analytics access logs to automatically detect column headers and initialize
          the business intelligence pipeline.
        </p>
      </div>

      {loading && <StatusBanner type="loading" message="Ingesting CSV file and detecting column headers..." />}
      {error && <StatusBanner type="error" message={error} onRetry={handleUpload} />}
      {success && <StatusBanner type="success" message={success} />}

      <div className="rounded-2xl border border-slate-200 bg-white p-6 sm:p-8 shadow-xs space-y-6">
        <CsvDropzone
          selectedFile={selectedFile}
          onFileSelect={handleFileSelect}
          disabled={loading}
        />

        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-t border-slate-100 pt-6">
          <div className="text-xs text-slate-500">
            {selectedFile ? (
              <span className="font-medium text-slate-700">
                1 file queued for upload ({selectedFile.name})
              </span>
            ) : (
              <span>Select or drop a .csv file to enable processing</span>
            )}
          </div>

          <button
            type="button"
            onClick={handleUpload}
            disabled={!selectedFile || loading}
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-indigo-600 px-6 py-3 text-sm font-semibold text-white shadow-xs hover:bg-indigo-700 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400 transition-all focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
          >
            {loading ? 'Uploading & Analyzing...' : 'Upload & Proceed to Mapping'}
            <ArrowRight className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
