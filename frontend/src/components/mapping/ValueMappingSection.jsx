import { AlertTriangle, CheckCircle2, ChevronRight, HelpCircle } from 'lucide-react';

export default function ValueMappingSection({
  uniqueValues = [],
  unknownValues = [],
  allowedActions = [],
  mapping,
  onChange,
  onSubmit,
  loading,
}) {
  const unknownSet = new Set(unknownValues);

  const handleValueChange = (rawVal, standardVal) => {
    onChange({
      ...mapping,
      [rawVal]: standardVal,
    });
  };

  const unmappedCount = uniqueValues.filter((v) => !mapping[v]).length;

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-6 sm:p-8 shadow-xs space-y-6">
      <div className="border-b border-slate-100 pb-5">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-indigo-600">
          Section 2 of 2
        </div>
        <h2 className="text-lg font-bold text-slate-900">Action Value Normalization</h2>
        <p className="mt-0.5 text-xs text-slate-500">
          Standardize distinct action tokens detected in your data into core behavioral event types.
        </p>
      </div>

      {unknownValues.length > 0 && (
        <div className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50/70 p-4 text-xs sm:text-sm text-amber-900 shadow-2xs">
          <AlertTriangle className="h-5 w-5 shrink-0 text-amber-600 mt-0.5" />
          <div className="space-y-1">
            <p className="font-bold">
              {unknownValues.length} unrecognized raw event{' '}
              {unknownValues.length === 1 ? 'action' : 'actions'} detected:
            </p>
            <p className="text-xs text-amber-800 leading-relaxed">
              Values like <code className="font-mono font-semibold">{unknownValues.join(', ')}</code>{' '}
              are not standard built-in aliases. Please map each value to an appropriate action or select{' '}
              <code className="font-mono font-semibold">other</code> before continuing.
            </p>
          </div>
        </div>
      )}

      <div className="overflow-x-auto rounded-xl border border-slate-200">
        <table className="w-full text-left text-xs sm:text-sm">
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50/70 text-[11px] font-bold uppercase tracking-wider text-slate-500">
              <th className="py-3 px-4">Raw Action in CSV</th>
              <th className="py-3 px-4">Classification</th>
              <th className="py-3 px-4">Normalized Standard Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {uniqueValues.map((rawVal) => {
              const isUnknown = unknownSet.has(rawVal) && !mapping[rawVal];
              const wasAutoUnknown = unknownSet.has(rawVal);
              const mappedValue = mapping[rawVal] || '';

              return (
                <tr
                  key={rawVal}
                  className={`transition-colors ${
                    isUnknown
                      ? 'bg-rose-50/30'
                      : wasAutoUnknown
                      ? 'bg-amber-50/30'
                      : 'hover:bg-slate-50/50'
                  }`}
                >
                  <td className="py-3.5 px-4 font-mono text-xs font-semibold text-slate-900">
                    {rawVal}
                  </td>
                  <td className="py-3.5 px-4">
                    {wasAutoUnknown ? (
                      <span className="inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-2.5 py-0.5 text-[11px] font-semibold text-amber-800">
                        <AlertTriangle className="h-3 w-3 text-amber-600" />
                        Unmapped Action
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-800">
                        <CheckCircle2 className="h-3 w-3 text-emerald-600" />
                        Recognized Alias
                      </span>
                    )}
                  </td>
                  <td className="py-3.5 px-4">
                    <div className="max-w-xs">
                      <label htmlFor={`val-${rawVal}`} className="sr-only">
                        Standard action for {rawVal}
                      </label>
                      <select
                        id={`val-${rawVal}`}
                        value={mappedValue}
                        onChange={(e) => handleValueChange(rawVal, e.target.value)}
                        disabled={loading}
                        className={`w-full rounded-xl border px-3 py-2 text-xs sm:text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:bg-slate-100 ${
                          !mappedValue
                            ? 'border-rose-300 bg-white text-rose-900'
                            : 'border-slate-300 bg-white text-slate-900'
                        }`}
                      >
                        <option value="">-- Choose Standard Action --</option>
                        {allowedActions.map((act) => (
                          <option key={act} value={act}>
                            {act}
                          </option>
                        ))}
                      </select>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-t border-slate-100 pt-6">
        <p className="text-xs text-slate-500">
          {unmappedCount > 0 ? (
            <span className="font-semibold text-rose-600">
              {unmappedCount} action {unmappedCount === 1 ? 'value' : 'values'} require mapping.
            </span>
          ) : (
            <span className="font-semibold text-emerald-700">
              All {uniqueValues.length} action values are mapped. Ready to clean and process.
            </span>
          )}
        </p>

        <button
          type="button"
          onClick={onSubmit}
          disabled={loading || uniqueValues.length === 0 || unmappedCount > 0}
          className="inline-flex items-center justify-center rounded-xl bg-indigo-600 px-6 py-3 text-xs sm:text-sm font-semibold text-white shadow-xs hover:bg-indigo-700 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400 transition-all focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
        >
          {loading ? 'Cleaning & Processing Records...' : 'Save Values & Process Dataset'}
        </button>
      </div>
    </section>
  );
}
