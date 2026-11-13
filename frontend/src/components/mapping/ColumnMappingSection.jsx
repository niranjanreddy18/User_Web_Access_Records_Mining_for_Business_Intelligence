import { CheckCircle2, ChevronRight, HelpCircle } from 'lucide-react';

const REQUIRED_FIELDS = [
  { key: 'user_id', label: 'User Identifier', description: 'Unique visitor ID, client IP, or user hash' },
  { key: 'timestamp', label: 'Event Timestamp', description: 'Date and time of activity (ISO, UTC, or standard string)' },
  { key: 'page_url', label: 'Page URL / Path', description: 'Resource or web route accessed (e.g. /home, /products)' },
  { key: 'action', label: 'Interaction Action', description: 'User event type (page_view, click, purchase, etc.)' },
];

const OPTIONAL_FIELDS = [
  { key: 'session_id', label: 'Existing Session ID', description: 'If populated, preserves existing session clusters' },
  { key: 'device', label: 'Device Category', description: 'Client device classification (mobile, desktop, tablet)' },
  { key: 'referrer', label: 'Referrer Source', description: 'HTTP referrer domain or external traffic origin' },
];

export default function ColumnMappingSection({
  headers = [],
  mapping,
  onChange,
  onSubmit,
  loading,
  submitted,
}) {
  const missingRequired = REQUIRED_FIELDS.filter((f) => !mapping[f.key]);

  const handleFieldChange = (appField, csvHeader) => {
    const next = { ...mapping };
    if (!csvHeader) {
      delete next[appField];
    } else {
      next[appField] = csvHeader;
    }
    onChange(next);
  };

  const renderFieldRow = (field, isRequired) => {
    const isMapped = Boolean(mapping[field.key]);
    const currentHeader = mapping[field.key] || '';

    return (
      <div
        key={field.key}
        className={`grid grid-cols-1 gap-3 rounded-xl border p-4 transition-colors sm:grid-cols-12 sm:items-center ${
          isMapped
            ? 'border-emerald-200 bg-emerald-50/20'
            : isRequired
            ? 'border-rose-200 bg-rose-50/20'
            : 'border-slate-200 bg-white'
        }`}
      >
        <div className="sm:col-span-6">
          <div className="flex items-center gap-2">
            <span className="text-sm font-bold text-slate-900">{field.label}</span>
            <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[11px] text-slate-700">
              {field.key}
            </code>
            {isRequired ? (
              <span className="rounded-full bg-rose-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-rose-800">
                Required
              </span>
            ) : (
              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-600">
                Optional
              </span>
            )}
          </div>
          <p className="mt-1 text-xs text-slate-500 leading-relaxed">{field.description}</p>
        </div>

        <div className="sm:col-span-6 flex items-center gap-2">
          <ChevronRight className="hidden sm:block h-4 w-4 text-slate-400 shrink-0" />
          <div className="w-full">
            <label htmlFor={`select-${field.key}`} className="sr-only">
              Map {field.label} to CSV header
            </label>
            <select
              id={`select-${field.key}`}
              value={currentHeader}
              onChange={(e) => handleFieldChange(field.key, e.target.value)}
              disabled={loading}
              className={`w-full rounded-xl border px-3.5 py-2.5 text-xs sm:text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:bg-slate-100 ${
                isMapped
                  ? 'border-emerald-300 bg-white text-slate-900'
                  : isRequired
                  ? 'border-rose-300 bg-white text-rose-900'
                  : 'border-slate-300 bg-white text-slate-700'
              }`}
            >
              <option value="">-- Select Source CSV Header --</option>
              {headers.map((header) => (
                <option key={header} value={header}>
                  {header}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>
    );
  };

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-6 sm:p-8 shadow-xs space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 pb-5">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-indigo-600">
            Section 1 of 2
          </div>
          <h2 className="text-lg font-bold text-slate-900">Source Column Mapping</h2>
          <p className="mt-0.5 text-xs text-slate-500">
            Assign detected CSV columns to the standardized application schema.
          </p>
        </div>
        {submitted && (
          <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-800">
            <CheckCircle2 className="h-3.5 w-3.5" />
            Columns Confirmed
          </span>
        )}
      </div>

      <div className="space-y-3">
        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">
          Required Schema Fields ({REQUIRED_FIELDS.length})
        </h3>
        <div className="space-y-2.5">{REQUIRED_FIELDS.map((f) => renderFieldRow(f, true))}</div>
      </div>

      <div className="space-y-3 pt-2">
        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">
          Optional Behavioral Dimensions ({OPTIONAL_FIELDS.length})
        </h3>
        <div className="space-y-2.5">{OPTIONAL_FIELDS.map((f) => renderFieldRow(f, false))}</div>
      </div>

      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-t border-slate-100 pt-6">
        <p className="text-xs text-slate-500">
          {missingRequired.length > 0 ? (
            <span className="font-semibold text-rose-600">
              Missing required fields: {missingRequired.map((f) => f.label).join(', ')}
            </span>
          ) : (
            <span className="font-semibold text-emerald-700">
              All required fields have been mapped successfully.
            </span>
          )}
        </p>

        <button
          type="button"
          onClick={onSubmit}
          disabled={loading || missingRequired.length > 0}
          className="inline-flex items-center justify-center rounded-xl bg-indigo-600 px-6 py-2.5 text-xs sm:text-sm font-semibold text-white shadow-xs hover:bg-indigo-700 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400 transition-all focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
        >
          {loading ? 'Saving Schema...' : submitted ? 'Update Column Mapping' : 'Save & Inspect Actions'}
        </button>
      </div>
    </section>
  );
}
