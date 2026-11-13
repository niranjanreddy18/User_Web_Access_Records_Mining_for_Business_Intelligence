import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, CheckCircle2, ShieldAlert, ShieldCheck, Sparkles } from 'lucide-react';
import { analyzeDataset } from '../api/analytics';
import { extractApiError } from '../api/client';
import { generateInsights } from '../api/insights';
import { minePatterns } from '../api/patterns';
import { getProcessingStatus, sessionizeDataset } from '../api/processing';
import StatusBanner, { SkeletonCard } from '../components/layout/StatusBanner';
import QualityMetricCard from '../components/processing/QualityMetricCard';
import { useJob } from '../hooks/useJob';

export default function QualityReport() {
  const navigate = useNavigate();
  const { jobId, qualityReport, updateJob, completeStep } = useJob();

  const [report, setReport] = useState(qualityReport);
  const [loadingReport, setLoadingReport] = useState(false);
  const [runningPipeline, setRunningPipeline] = useState(false);
  const [stageMessage, setStageMessage] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    if (!jobId || report) return;
    let active = true;
    setLoadingReport(true);
    getProcessingStatus(jobId)
      .then((data) => {
        if (!active) return;
        setReport(data.quality_report || {});
        updateJob({ qualityReport: data.quality_report || {} });
      })
      .catch((err) => {
        if (!active) return;
        setError(extractApiError(err, 'Unable to load data quality metrics.'));
      })
      .finally(() => {
        if (active) setLoadingReport(false);
      });
    return () => {
      active = false;
    };
  }, [jobId, report, updateJob]);

  const handleContinueAnalysis = async () => {
    if (runningPipeline) return;
    setRunningPipeline(true);
    setError('');

    try {
      setStageMessage('Phase 1/4: Clustering user events into sessions (30-min threshold)...');
      await sessionizeDataset(jobId, 30);

      setStageMessage('Phase 2/4: Computing behavioral analytics & distributions...');
      const analyzeRes = await analyzeDataset(jobId);

      setStageMessage('Phase 3/4: Mining frequent navigation sequences & transitions...');
      const patternsRes = await minePatterns(jobId, 0.1, 3);

      setStageMessage('Phase 4/4: Deriving data-grounded business insights...');
      const insightsRes = await generateInsights(jobId);

      updateJob({
        analytics: analyzeRes.analytics,
        patterns: patternsRes.patterns,
        insights: insightsRes.insights,
      });
      completeStep('quality', 'dashboard');
      navigate('/dashboard');
    } catch (err) {
      setError(
        extractApiError(
          err,
          'Unable to complete automated analysis. Please verify the dataset and try again.'
        )
      );
    } finally {
      setRunningPipeline(false);
      setStageMessage('');
    }
  };

  const missingRequiredCount =
    Number(report?.missing_user_id || 0) +
    Number(report?.missing_page_url || 0) +
    Number(report?.missing_action || 0);

  const retentionRate =
    report?.rows_before > 0
      ? ((Number(report.rows_after) / Number(report.rows_before)) * 100).toFixed(1)
      : '100.0';

  return (
    <div className="mx-auto max-w-5xl space-y-8">
      <div className="border-b border-slate-200 pb-5">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-indigo-600">
          <ShieldCheck className="h-4 w-4" />
          Step 3: Data Quality &amp; Hygiene Audit
        </div>
        <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
          Data Quality Report
        </h1>
        <p className="mt-1.5 text-sm text-slate-600">
          Inspection of raw log validity, dropped rows, deduplication results, and data readiness
          for downstream sessionization.
        </p>
      </div>

      {loadingReport && <StatusBanner type="loading" message="Loading quality report metrics..." />}
      {runningPipeline && <StatusBanner type="loading" message={stageMessage} />}
      {error && <StatusBanner type="error" message={error} onRetry={handleContinueAnalysis} />}

      {report && (
        <>
          {/* Readiness Banner */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 rounded-2xl border border-emerald-200 bg-emerald-50/60 p-6 shadow-2xs">
            <div className="flex items-start gap-4">
              <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-emerald-600 text-white shrink-0 shadow-2xs">
                <CheckCircle2 className="h-6 w-6" />
              </div>
              <div>
                <h2 className="text-base font-bold text-emerald-950">
                  Data Quality Validated &amp; Ready for Analysis
                </h2>
                <p className="mt-0.5 text-xs text-emerald-800 leading-relaxed">
                  {retentionRate}% of uploaded records passed hygiene criteria ({report.rows_after} valid rows).
                  Cleaned dataset is saved for session modeling.
                </p>
              </div>
            </div>
            <div className="text-right sm:border-l sm:border-emerald-200 sm:pl-6 shrink-0">
              <span className="block text-2xl font-extrabold text-emerald-950">{retentionRate}%</span>
              <span className="block text-[11px] font-medium text-emerald-700 uppercase tracking-wider">
                Health Score
              </span>
            </div>
          </div>

          {/* Metric Cards Grid */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <QualityMetricCard
              label="Rows Uploaded"
              value={report.rows_before}
              subtitle="Total raw lines extracted from CSV"
            />
            <QualityMetricCard
              label="Valid Rows Retained"
              value={report.rows_after}
              tone="success"
              subtitle="Records passed to session pipeline"
            />
            <QualityMetricCard
              label="Total Rows Removed"
              value={report.rows_removed}
              tone={report.rows_removed > 0 ? 'warning' : 'default'}
              subtitle="Corrupt, null, or invalid entries dropped"
            />
            <QualityMetricCard
              label="Duplicate Rows"
              value={report.duplicate_rows}
              tone={report.duplicate_rows > 0 ? 'warning' : 'default'}
              subtitle="Exact duplicate log occurrences"
            />
            <QualityMetricCard
              label="Invalid Timestamps"
              value={report.invalid_timestamp}
              tone={report.invalid_timestamp > 0 ? 'danger' : 'default'}
              subtitle="Unparseable date/time strings"
            />
            <QualityMetricCard
              label="Missing Required Values"
              value={missingRequiredCount}
              tone={missingRequiredCount > 0 ? 'danger' : 'default'}
              subtitle="Null user, URL, or action fields"
            />
          </div>

          {/* Action Trigger Card */}
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <h3 className="text-sm font-bold text-slate-900">Execute Automated Mining Pipeline</h3>
              <p className="mt-0.5 text-xs text-slate-500">
                Clusters events into sessions (30m gap threshold), computes analytics, mines frequent
                navigation sequences, and outputs BI insights.
              </p>
            </div>

            <button
              type="button"
              onClick={handleContinueAnalysis}
              disabled={runningPipeline}
              className="inline-flex items-center justify-center gap-2 rounded-xl bg-indigo-600 px-7 py-3.5 text-sm font-semibold text-white shadow-xs hover:bg-indigo-700 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400 transition-all focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 shrink-0"
            >
              {runningPipeline ? 'Computing Pipeline...' : 'Continue to Session Analysis'}
              <ArrowRight className="h-4 w-4" />
            </button>
          </div>
        </>
      )}
    </div>
  );
}
