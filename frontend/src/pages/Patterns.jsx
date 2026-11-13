import { useEffect, useState } from 'react';
import { ArrowRight, Compass, GitBranch, Layers, TrendingUp } from 'lucide-react';
import { extractApiError } from '../api/client';
import { getPatterns } from '../api/patterns';
import StatusBanner, { SkeletonCard } from '../components/layout/StatusBanner';
import { useJob } from '../hooks/useJob';
import { formatNumber, formatPercent } from '../utils/formatters';

export default function Patterns() {
  const { jobId, filename, patterns: cachedPatterns, updateJob } = useJob();
  const [patterns, setPatterns] = useState(cachedPatterns);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const fetchPatterns = () => {
    if (!jobId) return;
    setLoading(true);
    setError('');
    getPatterns(jobId)
      .then((data) => {
        const result = data.patterns || {};
        setPatterns(result);
        updateJob({ patterns: result });
      })
      .catch((err) => {
        setError(extractApiError(err, 'Unable to load sequential patterns.'));
      })
      .finally(() => {
        setLoading(false);
      });
  };

  useEffect(() => {
    if (!jobId || patterns) return;
    fetchPatterns();
  }, [jobId]);

  if (loading) {
    return (
      <div className="space-y-6">
        <StatusBanner type="loading" message="Mining sequential navigation patterns &amp; transitions..." />
        <SkeletonCard height="h-64" />
        <SkeletonCard height="h-64" />
      </div>
    );
  }

  if (error) {
    return (
      <StatusBanner
        type="error"
        message={error}
        onRetry={fetchPatterns}
      />
    );
  }

  if (!patterns) {
    return (
      <StatusBanner
        type="info"
        message="Pattern mining results are not available yet. Please complete session analysis first."
      />
    );
  }

  const commonJourneys = patterns.common_journeys || patterns.page_patterns || [];
  const transitions = patterns.transitions || [];
  const actionPatterns = patterns.action_patterns || [];

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-indigo-600">
            <GitBranch className="h-4 w-4" />
            Sequential Pattern Mining
          </div>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
            User Navigation &amp; Action Paths
          </h1>
          <p className="mt-1 text-xs text-slate-500">
            Chronological contiguous patterns extracted from sessions in:{' '}
            <span className="font-semibold text-slate-700">{filename || jobId}</span>
          </p>
        </div>

        <div className="flex items-center gap-2 text-xs font-semibold text-indigo-700 bg-indigo-50 border border-indigo-200 rounded-xl px-3.5 py-2 shadow-2xs self-start sm:self-auto">
          <span>Min Support: 10% • Length: 2–3</span>
        </div>
      </div>

      {/* Common User Journeys */}
      <section className="rounded-2xl border border-slate-200 bg-white p-6 sm:p-8 shadow-xs space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-100 pb-4">
          <div>
            <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-500">
              <Compass className="h-4 w-4 text-indigo-600" /> Page Flow
            </div>
            <h2 className="text-base font-bold text-slate-900">Common User Journeys</h2>
            <p className="text-xs text-slate-500">
              Contiguous multi-step page view paths that recur across distinct user sessions
            </p>
          </div>
          <span className="rounded-full bg-indigo-50 border border-indigo-200 px-3 py-1 text-xs font-bold text-indigo-700 self-start sm:self-auto">
            {commonJourneys.length} Journeys Discovered
          </span>
        </div>

        {commonJourneys.length === 0 ? (
          <div className="py-12 text-center text-xs text-slate-400">
            No page sequences met the minimum support threshold (10%).
          </div>
        ) : (
          <div className="overflow-x-auto rounded-xl border border-slate-200">
            <table className="w-full text-left text-xs sm:text-sm">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50/70 text-[11px] font-bold uppercase tracking-wider text-slate-500">
                  <th className="py-3 px-4">Navigation Sequence</th>
                  <th className="py-3 px-4">Length</th>
                  <th className="py-3 px-4 text-right">Unique Sessions</th>
                  <th className="py-3 px-4 text-right">Support Share</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {commonJourneys.map((item, idx) => (
                  <tr key={`journey-${idx}`} className="hover:bg-slate-50/50 transition-colors">
                    <td className="py-3.5 px-4">
                      <div className="flex flex-wrap items-center gap-1.5 font-mono text-xs">
                        {item.pattern.map((page, pIdx) => (
                          <span key={pIdx} className="inline-flex items-center gap-1.5">
                            <span className="rounded-lg bg-slate-100 border border-slate-200 px-2.5 py-1 text-slate-900 font-semibold shadow-2xs">
                              {page}
                            </span>
                            {pIdx < item.pattern.length - 1 && (
                              <ArrowRight className="h-3.5 w-3.5 text-indigo-500 shrink-0" />
                            )}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="py-3.5 px-4 text-xs font-medium text-slate-500">
                      {item.length} steps
                    </td>
                    <td className="py-3.5 px-4 text-right font-extrabold text-slate-900">
                      {formatNumber(item.session_count)}
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <span className="inline-flex rounded-full bg-indigo-50 border border-indigo-200 px-2.5 py-0.5 text-xs font-bold text-indigo-700">
                        {formatPercent(item.support)}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Frequent Page Transitions */}
      <section className="rounded-2xl border border-slate-200 bg-white p-6 sm:p-8 shadow-xs space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-100 pb-4">
          <div>
            <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-500">
              <TrendingUp className="h-4 w-4 text-emerald-600" /> Adjacent Edges
            </div>
            <h2 className="text-base font-bold text-slate-900">Frequent Page Transitions</h2>
            <p className="text-xs text-slate-500">
              Direct transitions between consecutive page views ranked by session count
            </p>
          </div>
          <span className="rounded-full bg-emerald-50 border border-emerald-200 px-3 py-1 text-xs font-bold text-emerald-800 self-start sm:self-auto">
            Top {transitions.length} Transitions
          </span>
        </div>

        {transitions.length === 0 ? (
          <div className="py-12 text-center text-xs text-slate-400">
            No adjacent page transitions recorded.
          </div>
        ) : (
          <div className="overflow-x-auto rounded-xl border border-slate-200">
            <table className="w-full text-left text-xs sm:text-sm">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50/70 text-[11px] font-bold uppercase tracking-wider text-slate-500">
                  <th className="py-3 px-4">Origin Page (From)</th>
                  <th className="py-3 px-4">Destination Page (To)</th>
                  <th className="py-3 px-4 text-right">Unique Sessions</th>
                  <th className="py-3 px-4 text-right">Total Transitions</th>
                  <th className="py-3 px-4 text-right">Session Support</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {transitions.map((item, idx) => (
                  <tr key={`trans-${idx}`} className="hover:bg-slate-50/50 transition-colors">
                    <td className="py-3.5 px-4 font-mono text-xs font-semibold text-slate-800">
                      {item.from}
                    </td>
                    <td className="py-3.5 px-4 font-mono text-xs font-semibold text-slate-800">
                      {item.to}
                    </td>
                    <td className="py-3.5 px-4 text-right font-extrabold text-slate-900">
                      {formatNumber(item.unique_sessions)}
                    </td>
                    <td className="py-3.5 px-4 text-right text-xs text-slate-500 font-medium">
                      {formatNumber(item.transition_count)}
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <span className="inline-flex rounded-full bg-emerald-50 border border-emerald-200 px-2.5 py-0.5 text-xs font-bold text-emerald-800">
                        {formatPercent(item.support)}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Action Sequences */}
      <section className="rounded-2xl border border-slate-200 bg-white p-6 sm:p-8 shadow-xs space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-100 pb-4">
          <div>
            <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-500">
              <Layers className="h-4 w-4 text-indigo-600" /> Event Sequences
            </div>
            <h2 className="text-base font-bold text-slate-900">Frequent Action Sequences</h2>
            <p className="text-xs text-slate-500">
              Subsequent user actions occurring in sequence (e.g. view → add_to_cart → purchase)
            </p>
          </div>
          <span className="rounded-full bg-slate-100 border border-slate-200 px-3 py-1 text-xs font-bold text-slate-700 self-start sm:self-auto">
            {actionPatterns.length} Patterns
          </span>
        </div>

        {actionPatterns.length === 0 ? (
          <div className="py-12 text-center text-xs text-slate-400">
            No action sequences met the minimum support threshold.
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {actionPatterns.map((item, idx) => (
              <div
                key={`act-${idx}`}
                className="rounded-xl border border-slate-200 bg-slate-50/70 p-4 space-y-3 shadow-2xs hover:shadow-xs transition-shadow"
              >
                <div className="flex flex-wrap items-center gap-1.5 font-mono text-xs">
                  {item.pattern.map((act, aIdx) => (
                    <span key={aIdx} className="inline-flex items-center gap-1.5">
                      <span className="rounded-md bg-white border border-slate-200 px-2 py-0.5 font-bold text-indigo-700 shadow-2xs">
                        {act}
                      </span>
                      {aIdx < item.pattern.length - 1 && (
                        <ArrowRight className="h-3 w-3 text-slate-400" />
                      )}
                    </span>
                  ))}
                </div>

                <div className="flex items-center justify-between text-xs pt-2 border-t border-slate-200/70 font-medium">
                  <span className="text-slate-500">{formatNumber(item.session_count)} sessions</span>
                  <span className="font-bold text-indigo-700">{formatPercent(item.support)}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
