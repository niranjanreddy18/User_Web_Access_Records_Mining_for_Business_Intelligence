export default function QualityMetricCard({ label, value, tone = 'default', subtitle }) {
  const toneClasses = {
    default: 'border-slate-200 bg-white text-slate-900',
    success: 'border-emerald-200 bg-emerald-50/40 text-emerald-950',
    warning: 'border-amber-200 bg-amber-50/40 text-amber-950',
    danger: 'border-rose-200 bg-rose-50/40 text-rose-950',
  };

  const badgeClasses = {
    default: 'bg-slate-100 text-slate-700',
    success: 'bg-emerald-100 text-emerald-800',
    warning: 'bg-amber-100 text-amber-800',
    danger: 'bg-rose-100 text-rose-800',
  };

  return (
    <div className={`rounded-2xl border p-6 shadow-xs flex flex-col justify-between ${toneClasses[tone] || toneClasses.default}`}>
      <div>
        <div className="flex items-center justify-between">
          <p className="text-xs font-bold uppercase tracking-wider text-slate-500">{label}</p>
          <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${badgeClasses[tone] || badgeClasses.default}`}>
            {tone === 'success' ? 'Retained' : tone === 'danger' || tone === 'warning' ? 'Check' : 'Audit'}
          </span>
        </div>
        <p className="mt-3 text-3xl font-extrabold tracking-tight">{Number(value ?? 0).toLocaleString()}</p>
      </div>
      {subtitle && <p className="mt-2 text-xs text-slate-500 font-medium">{subtitle}</p>}
    </div>
  );
}
