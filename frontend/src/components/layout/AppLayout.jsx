import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  Activity,
  BarChart3,
  CheckCircle2,
  Database,
  FileSpreadsheet,
  GitBranch,
  Lightbulb,
  Lock,
  Menu,
  ShieldCheck,
  SlidersHorizontal,
  X,
} from 'lucide-react';
import { WORKFLOW_STEPS, useJob } from '../../hooks/useJob';

const STEP_ICONS = {
  upload: FileSpreadsheet,
  mapping: SlidersHorizontal,
  quality: ShieldCheck,
  dashboard: BarChart3,
  patterns: GitBranch,
  insights: Lightbulb,
};

export default function AppLayout({ children }) {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const location = useLocation();
  const { jobId, filename, completedSteps, canAccessStep, resetJob } = useJob();

  const renderSidebarLinks = () => (
    <nav className="space-y-1.5" aria-label="Workflow pipeline">
      {WORKFLOW_STEPS.map((step, index) => {
        const Icon = STEP_ICONS[step.key] || Activity;
        const isCurrent = location.pathname === step.path;
        const isCompleted = completedSteps.includes(step.key);
        const accessible = canAccessStep(step.key);

        if (!accessible) {
          return (
            <div
              key={step.key}
              className="flex items-center justify-between rounded-xl px-3.5 py-3 text-xs font-medium text-slate-400 bg-slate-50/50 cursor-not-allowed select-none border border-transparent"
              title="Prerequisite steps must be completed first"
            >
              <div className="flex items-center gap-3 min-w-0">
                <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-slate-200/60 text-[11px] font-semibold text-slate-500 shrink-0">
                  {index + 1}
                </span>
                <div className="min-w-0">
                  <span className="block font-medium text-slate-500 truncate">{step.label}</span>
                  <span className="block text-[11px] text-slate-400 truncate">{step.subtitle}</span>
                </div>
              </div>
              <Lock className="h-3.5 w-3.5 text-slate-400 shrink-0 ml-2" />
            </div>
          );
        }

        return (
          <Link
            key={step.key}
            to={step.path}
            onClick={() => setMobileMenuOpen(false)}
            className={`group flex items-center justify-between rounded-xl px-3.5 py-3 text-xs font-medium transition-all ${
              isCurrent
                ? 'bg-indigo-600 text-white shadow-xs font-semibold'
                : 'text-slate-700 hover:bg-slate-100 hover:text-slate-900'
            }`}
          >
            <div className="flex items-center gap-3 min-w-0">
              <span
                className={`flex h-7 w-7 items-center justify-center rounded-lg text-[11px] font-semibold shrink-0 transition-colors ${
                  isCurrent
                    ? 'bg-indigo-500/50 text-white'
                    : isCompleted
                    ? 'bg-emerald-100 text-emerald-800'
                    : 'bg-slate-100 text-slate-700'
                }`}
              >
                {isCompleted ? <CheckCircle2 className="h-4 w-4 text-emerald-700" /> : index + 1}
              </span>
              <div className="min-w-0">
                <span className={`block font-medium truncate ${isCurrent ? 'text-white' : 'text-slate-900'}`}>
                  {step.label}
                </span>
                <span className={`block text-[11px] truncate ${isCurrent ? 'text-indigo-200' : 'text-slate-500'}`}>
                  {step.subtitle}
                </span>
              </div>
            </div>
            <Icon
              className={`h-4 w-4 shrink-0 ml-2 ${
                isCurrent ? 'text-indigo-200' : isCompleted ? 'text-emerald-600' : 'text-slate-400'
              }`}
            />
          </Link>
        );
      })}
    </nav>
  );

  return (
    <div className="min-h-screen flex flex-col bg-slate-50 text-slate-900 antialiased selection:bg-indigo-500 selection:text-white">
      {/* Top Application Bar */}
      <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/95 backdrop-blur-xs">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setMobileMenuOpen((v) => !v)}
              className="inline-flex items-center justify-center rounded-lg p-2 text-slate-600 hover:bg-slate-100 lg:hidden"
              aria-label="Toggle navigation menu"
            >
              {mobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </button>
            <Link to="/" className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-600 text-white shadow-xs">
                <Activity className="h-5 w-5" />
              </div>
              <div>
                <span className="text-base font-bold tracking-tight text-slate-900 block leading-tight">
                  Web Access Mining
                </span>
                <span className="text-xs font-medium text-slate-500 hidden sm:block">
                  Business Intelligence &amp; Pattern Discovery
                </span>
              </div>
            </Link>
          </div>

          <div className="flex items-center gap-3">
            {jobId ? (
              <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-1.5 shadow-2xs">
                <div className="flex h-6 w-6 items-center justify-center rounded-md bg-emerald-50 text-emerald-700">
                  <Database className="h-3.5 w-3.5" />
                </div>
                <div className="text-left">
                  <span className="block text-[11px] font-semibold text-slate-800 leading-tight max-w-[120px] sm:max-w-[200px] truncate">
                    {filename || 'Active Dataset'}
                  </span>
                  <span className="block text-[10px] text-slate-400 font-mono leading-tight">
                    {jobId.slice(0, 8)}...
                  </span>
                </div>
                <button
                  type="button"
                  onClick={resetJob}
                  className="ml-1 text-[11px] font-semibold text-slate-500 hover:text-indigo-600 transition-colors"
                  title="Clear active dataset session"
                >
                  Reset
                </button>
              </div>
            ) : (
              <span className="rounded-lg border border-slate-200 bg-slate-100 px-3 py-1.5 text-xs font-medium text-slate-600">
                No active dataset loaded
              </span>
            )}
          </div>
        </div>
      </header>

      {/* Main Workspace */}
      <div className="mx-auto flex w-full max-w-7xl flex-1">
        <aside className="hidden w-72 shrink-0 border-r border-slate-200 bg-white p-5 lg:block">
          <div className="mb-4 px-2 flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
              Pipeline Steps
            </span>
            <span className="text-[11px] font-medium text-slate-400">
              {completedSteps.length} of 6 ready
            </span>
          </div>
          {renderSidebarLinks()}

          <div className="mt-8 rounded-xl border border-slate-200 bg-slate-50/70 p-4">
            <div className="flex items-center gap-2 text-xs font-semibold text-slate-700">
              <ShieldCheck className="h-4 w-4 text-indigo-600" />
              Pipeline Architecture
            </div>
            <p className="mt-1.5 text-[11px] leading-relaxed text-slate-500">
              Ingests raw web access CSVs, standardizes schemas, clusters events into sessions with a
              30m timeout, extracts contiguous patterns, and surfaces data-grounded insights.
            </p>
          </div>
        </aside>

        {mobileMenuOpen && (
          <div className="fixed inset-0 top-16 z-20 bg-slate-900/40 backdrop-blur-2xs lg:hidden">
            <aside className="h-full w-72 bg-white p-5 shadow-2xl">
              <div className="mb-4 px-2 flex items-center justify-between">
                <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                  Pipeline Steps
                </span>
              </div>
              {renderSidebarLinks()}
            </aside>
          </div>
        )}

        <main className="flex-1 min-w-0 p-4 sm:p-6 lg:p-8">{children}</main>
      </div>
    </div>
  );
}
