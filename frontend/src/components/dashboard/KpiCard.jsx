export default function KpiCard({ label, value, subtitle, icon: Icon, badge }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs flex flex-col justify-between transition-shadow hover:shadow-md">
      <div>
        <div className="flex items-center justify-between">
          <p className="text-xs font-bold uppercase tracking-wider text-slate-500">{label}</p>
          {Icon && (
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-50 text-indigo-600">
              <Icon className="h-4 w-4" />
            </div>
          )}
        </div>
        <p className="mt-3 text-3xl font-extrabold tracking-tight text-slate-900">{value}</p>
      </div>

      {(subtitle || badge) && (
        <div className="mt-3 flex items-center justify-between border-t border-slate-100 pt-2 text-xs">
          {subtitle && <span className="text-slate-500 font-medium">{subtitle}</span>}
          {badge && (
            <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-600">
              {badge}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
