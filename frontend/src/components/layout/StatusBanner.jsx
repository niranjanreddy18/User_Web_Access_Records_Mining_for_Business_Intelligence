import { AlertCircle, CheckCircle2, Info, Loader2, RotateCcw } from 'lucide-react';

export default function StatusBanner({ type = 'info', message, onRetry }) {
  if (!message) return null;

  const styles = {
    loading: 'border-indigo-200 bg-indigo-50/70 text-indigo-900',
    error: 'border-rose-200 bg-rose-50/70 text-rose-900',
    success: 'border-emerald-200 bg-emerald-50/70 text-emerald-900',
    info: 'border-slate-200 bg-slate-50 text-slate-800',
  };

  const icons = {
    loading: <Loader2 className="h-5 w-5 animate-spin shrink-0 text-indigo-600" />,
    error: <AlertCircle className="h-5 w-5 shrink-0 text-rose-600" />,
    success: <CheckCircle2 className="h-5 w-5 shrink-0 text-emerald-600" />,
    info: <Info className="h-5 w-5 shrink-0 text-slate-600" />,
  };

  return (
    <div
      role="status"
      className={`flex items-start justify-between gap-3 rounded-xl border p-4 text-sm shadow-xs ${
        styles[type] || styles.info
      }`}
    >
      <div className="flex items-start gap-3">
        <span className="mt-0.5">{icons[type] || icons.info}</span>
        <div className="leading-relaxed font-medium">{message}</div>
      </div>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="inline-flex items-center gap-1.5 rounded-lg border border-rose-300 bg-white px-3 py-1.5 text-xs font-semibold text-rose-700 shadow-2xs hover:bg-rose-50 transition-colors shrink-0"
        >
          <RotateCcw className="h-3.5 w-3.5" />
          Try Again
        </button>
      )}
    </div>
  );
}

export function SkeletonCard({ height = 'h-28' }) {
  return (
    <div className={`animate-pulse rounded-xl border border-slate-200 bg-slate-100/60 p-5 ${height}`} />
  );
}

export function SkeletonChart({ height = 'h-72' }) {
  return (
    <div className={`animate-pulse rounded-xl border border-slate-200 bg-white p-6 shadow-xs ${height}`}>
      <div className="h-4 w-1/3 bg-slate-200 rounded mb-2" />
      <div className="h-3 w-1/4 bg-slate-100 rounded mb-6" />
      <div className="h-44 w-full bg-slate-100 rounded" />
    </div>
  );
}
