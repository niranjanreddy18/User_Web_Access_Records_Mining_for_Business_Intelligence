import { useRef, useState } from 'react';
import { CheckCircle2, FileSpreadsheet, HardDrive, Info, UploadCloud } from 'lucide-react';
import { formatFileSize } from '../../utils/formatters';

export default function CsvDropzone({ selectedFile, onFileSelect, disabled }) {
  const inputRef = useRef(null);
  const [isDragging, setIsDragging] = useState(false);

  const handleFiles = (files) => {
    if (!files || files.length === 0) return;
    onFileSelect(files[0]);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    if (!disabled) setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    if (disabled) return;
    handleFiles(e.dataTransfer.files);
  };

  return (
    <div className="space-y-4">
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => !disabled && inputRef.current?.click()}
        tabIndex={disabled ? -1 : 0}
        onKeyDown={(e) => {
          if (!disabled && (e.key === 'Enter' || e.key === ' ')) {
            e.preventDefault();
            inputRef.current?.click();
          }
        }}
        className={`group relative flex flex-col items-center justify-center rounded-2xl border-2 border-dashed p-12 text-center transition-all ${
          disabled
            ? 'border-slate-200 bg-slate-50 cursor-not-allowed opacity-75'
            : isDragging
            ? 'border-indigo-600 bg-indigo-50/60 cursor-pointer scale-[1.005]'
            : 'border-slate-300 bg-white hover:border-indigo-500 hover:bg-slate-50/70 cursor-pointer'
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".csv,text/csv"
          disabled={disabled}
          onChange={(e) => handleFiles(e.target.files)}
          className="hidden"
          aria-label="Upload CSV log file"
        />

        <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-600 shadow-2xs group-hover:scale-105 transition-transform">
          <UploadCloud className="h-7 w-7" />
        </div>

        <p className="text-base font-bold text-slate-900">
          Drop your CSV file here, or{' '}
          <span className="text-indigo-600 group-hover:underline">browse disk</span>
        </p>

        <p className="mt-1.5 max-w-sm text-xs text-slate-500 leading-relaxed">
          Supports standard or non-standard server logs. Maximum file size: 50 MB.
        </p>

        <div className="mt-6 flex flex-wrap items-center justify-center gap-2 text-[11px] font-medium text-slate-500">
          <span className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-2 py-1">
            <CheckCircle2 className="h-3 w-3 text-emerald-600" /> user_id
          </span>
          <span className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-2 py-1">
            <CheckCircle2 className="h-3 w-3 text-emerald-600" /> timestamp
          </span>
          <span className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-2 py-1">
            <CheckCircle2 className="h-3 w-3 text-emerald-600" /> page_url
          </span>
          <span className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-2 py-1">
            <CheckCircle2 className="h-3 w-3 text-emerald-600" /> action
          </span>
          <span className="text-slate-400">+(device, session, referrer)</span>
        </div>
      </div>

      {selectedFile && (
        <div className="flex items-center justify-between rounded-xl border border-indigo-200 bg-indigo-50/50 px-4 py-3.5 shadow-2xs">
          <div className="flex items-center gap-3 min-w-0">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-indigo-600 text-white shrink-0">
              <FileSpreadsheet className="h-5 w-5" />
            </div>
            <div className="min-w-0">
              <p className="truncate text-sm font-bold text-slate-900">{selectedFile.name}</p>
              <div className="flex items-center gap-2 text-xs text-slate-500">
                <span>{formatFileSize(selectedFile.size)}</span>
                <span>•</span>
                <span className="font-medium text-emerald-700">Ready for intake</span>
              </div>
            </div>
          </div>
          <button
            type="button"
            disabled={disabled}
            onClick={() => inputRef.current?.click()}
            className="rounded-lg border border-indigo-200 bg-white px-3 py-1.5 text-xs font-semibold text-indigo-700 shadow-2xs hover:bg-indigo-50 disabled:opacity-50 transition-colors"
          >
            Change File
          </button>
        </div>
      )}
    </div>
  );
}
