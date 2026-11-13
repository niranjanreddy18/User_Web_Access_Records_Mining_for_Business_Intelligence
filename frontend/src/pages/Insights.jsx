import { useEffect, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  Compass,
  FileText,
  Info,
  Layers,
  Lightbulb,
  Smartphone,
  Sparkles,
  TrendingUp,
} from 'lucide-react';
import { extractApiError } from '../api/client';
import { getInsights } from '../api/insights';
import StatusBanner, { SkeletonCard } from '../components/layout/StatusBanner';
import { useJob } from '../hooks/useJob';

const SEVERITY_CONFIG = {
  positive: {
    border: 'border-emerald-200',
    bg: 'bg-emerald-50/40',
    badge: 'bg-emerald-100 border border-emerald-200 text-emerald-800',
    icon: CheckCircle2,
    iconColor: 'text-emerald-600',
    glow: 'shadow-emerald-500/5',
  },
  warning: {
    border: 'border-amber-200',
    bg: 'bg-amber-50/40',
    badge: 'bg-amber-100 border border-amber-200 text-amber-800',
    icon: AlertTriangle,
    iconColor: 'text-amber-600',
    glow: 'shadow-amber-500/5',
  },
  info: {
    border: 'border-slate-200',
    bg: 'bg-white',
    badge: 'bg-indigo-50 border border-indigo-200 text-indigo-700',
    icon: Info,
    iconColor: 'text-indigo-600',
    glow: 'shadow-slate-500/5',
  },
};

const TYPE_ICONS = {
  traffic: TrendingUp,
  engagement: Layers,
  content: FileText,
  navigation: Compass,
  device: Smartphone,
  conversion: Sparkles,
  exit: Info,
};

export default function Insights() {
  const { jobId, filename, insights: cachedInsights, updateJob } = useJob();
  const [insights, setInsights] = useState(cachedInsights);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const fetchInsights = () => {
    if (!jobId) return;
    setLoading(true);
    setError('');
    getInsights(jobId)
      .then((data) => {
        const result = data.insights || [];
        setInsights(result);
        updateJob({ insights: result });
      })
      .catch((err) => {
        setError(extractApiError(err, 'Unable to load business intelligence insights.'));
      })
      .finally(() => {
        setLoading(false);
      });
  };

  useEffect(() => {
    if (!jobId || insights) return;
    fetchInsights();
  }, [jobId]);

  if (loading) {
    return (
      <div className="space-y-6">
        <StatusBanner type="loading" message="Loading business intelligence observations..." />
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <SkeletonCard height="h-44" />
          <SkeletonCard height="h-44" />
          <SkeletonCard height="h-44" />
          <SkeletonCard height="h-44" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <StatusBanner
        type="error"
        message={error}
        onRetry={fetchInsights}
      />
    );
  }

  if (!insights || insights.length === 0) {
    return (
      <StatusBanner
        type="info"
        message="No insights have been calculated yet. Please run session analysis from the Data Quality page."
      />
    );
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-indigo-600">
            <Lightbulb className="h-4 w-4" />
            Business Intelligence Insights
          </div>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
            Executive Summary &amp; Findings
          </h1>
          <p className="mt-1 text-xs text-slate-500">
            Deterministic rule-based observations derived from dataset:{' '}
            <span className="font-semibold text-slate-700">{filename || jobId}</span>
          </p>
        </div>

        <div className="flex items-center gap-2 text-xs font-semibold text-slate-700 bg-white border border-slate-200 rounded-xl px-3.5 py-2 shadow-2xs self-start sm:self-auto">
          <span>{insights.length} Data-Backed Observations</span>
        </div>
      </div>

      {/* Insights Cards Grid */}
      <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
        {insights.map((insight, idx) => {
          const sev = SEVERITY_CONFIG[insight.severity] || SEVERITY_CONFIG.info;
          const TypeIcon = TYPE_ICONS[insight.type] || Info;
          const metric = insight.metric;

          return (
            <div
              key={`insight-${idx}`}
              className={`rounded-2xl border p-6 shadow-xs transition-all hover:shadow-md flex flex-col justify-between ${sev.border} ${sev.bg}`}
            >
              <div>
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-2.5">
                    <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-white shadow-2xs border border-slate-200">
                      <TypeIcon className="h-4 w-4 text-slate-700" />
                    </div>
                    <div>
                      <h2 className="text-base font-bold text-slate-900 leading-tight">
                        {insight.title}
                      </h2>
                      <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                        {insight.type}
                      </span>
                    </div>
                  </div>

                  <span
                    className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider ${sev.badge}`}
                  >
                    {insight.severity}
                  </span>
                </div>

                <p className="mt-4 text-sm leading-relaxed text-slate-800 font-medium">
                  {insight.message}
                </p>
              </div>

              {/* Supporting Metric Pill */}
              {metric && (
                <div className="mt-5 border-t border-slate-200/60 pt-3 flex items-center justify-between text-xs">
                  <span className="font-mono text-[11px] text-slate-400 uppercase tracking-wider">
                    Metric: {metric.name}
                  </span>
                  <span className="rounded-md bg-white border border-slate-200 px-2 py-0.5 font-mono text-[11px] font-bold text-slate-700 shadow-2xs">
                    {typeof metric.value === 'object'
                      ? JSON.stringify(metric.value).slice(0, 32)
                      : String(metric.value)}
                  </span>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
