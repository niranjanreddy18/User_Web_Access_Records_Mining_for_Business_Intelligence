import { Link } from 'react-router-dom';
import {
  ArrowRight,
  BarChart3,
  Clock,
  Compass,
  Database,
  FileSpreadsheet,
  GitBranch,
  Layers,
  Lightbulb,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';

const WORKFLOW_CARDS = [
  {
    step: '01',
    title: 'Upload CSV',
    desc: 'Ingest raw web access records with support for custom headers and various formats.',
    icon: FileSpreadsheet,
  },
  {
    step: '02',
    title: 'Normalize & Clean',
    desc: 'Map heterogeneous columns and action aliases into a consistent standard schema.',
    icon: Layers,
  },
  {
    step: '03',
    title: 'Identify Sessions',
    desc: 'Cluster chronological events into distinct user sessions using inactivity timeouts.',
    icon: Clock,
  },
  {
    step: '04',
    title: 'Mine Patterns',
    desc: 'Discover frequent navigation paths, contiguous journeys, and page transitions.',
    icon: GitBranch,
  },
  {
    step: '05',
    title: 'Business Insights',
    desc: 'Generate deterministic, data-backed observations for actionable decisions.',
    icon: Lightbulb,
  },
];

const HIGHLIGHTS = [
  {
    title: 'Dynamic Schema Adaptation',
    desc: 'Intelligently detects user ID, timestamp, URL, action, device, and referrer fields from different server logs.',
    icon: Database,
  },
  {
    title: 'Deterministic Rules Engine',
    desc: 'Zero hallucinated statistics: every metric and insight is derived directly from backend Pandas analytics.',
    icon: ShieldCheck,
  },
  {
    title: 'Executive BI Dashboard',
    desc: 'Interactive Recharts visualizations covering traffic cycles, page volume, action mix, and device distributions.',
    icon: BarChart3,
  },
];

export default function Home() {
  return (
    <div className="mx-auto max-w-6xl space-y-12 py-2">
      {/* Hero Banner */}
      <section className="relative overflow-hidden rounded-2xl border border-slate-200 bg-white p-8 shadow-xs sm:p-12 lg:p-16">
        <div className="relative z-10 max-w-3xl space-y-6">
          <div className="inline-flex items-center gap-2 rounded-full border border-indigo-200 bg-indigo-50/80 px-3.5 py-1 text-xs font-semibold text-indigo-700">
            <Sparkles className="h-3.5 w-3.5" />
            Web Access Analytics &amp; Business Intelligence Platform
          </div>

          <h1 className="text-3xl font-extrabold tracking-tight text-slate-900 sm:text-4xl lg:text-5xl leading-tight">
            Transform Raw Web Access Logs into Actionable Business Intelligence
          </h1>

          <p className="text-base sm:text-lg leading-relaxed text-slate-600">
            Upload web server and monitoring access records. Automatically clean and normalize schema
            differences, reconstruct user sessions with chronological precision, mine high-frequency
            navigation paths, and uncover grounded business insights.
          </p>

          <div className="pt-2 flex flex-wrap items-center gap-4">
            <Link
              to="/upload"
              className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-7 py-3.5 text-sm font-semibold text-white shadow-xs hover:bg-indigo-700 transition-all focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
            >
              Analyze CSV
              <ArrowRight className="h-4 w-4" />
            </Link>
            <div className="flex items-center gap-2 text-xs font-medium text-slate-500">
              <ShieldCheck className="h-4 w-4 text-emerald-600" />
              Handles up to 50 MB / 100,000 records
            </div>
          </div>
        </div>
      </section>

      {/* Step by Step Workflow */}
      <section className="space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-2 border-b border-slate-200 pb-4">
          <div>
            <h2 className="text-xl font-bold tracking-tight text-slate-900">Analysis Pipeline Flow</h2>
            <p className="mt-1 text-xs text-slate-500">
              How your raw access records flow from ingestion to final business intelligence
            </p>
          </div>
          <span className="text-xs font-semibold uppercase tracking-wider text-indigo-600">
            5-Stage Automated Architecture
          </span>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {WORKFLOW_CARDS.map((card) => {
            const Icon = card.icon;
            return (
              <div
                key={card.step}
                className="relative rounded-xl border border-slate-200 bg-white p-5 shadow-xs transition-shadow hover:shadow-md flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <span className="font-mono text-xs font-bold text-slate-400">STAGE {card.step}</span>
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-50 text-indigo-600">
                      <Icon className="h-4 w-4" />
                    </div>
                  </div>
                  <h3 className="text-sm font-bold text-slate-900">{card.title}</h3>
                  <p className="mt-1.5 text-xs leading-relaxed text-slate-500">{card.desc}</p>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* Product Highlights */}
      <section className="grid grid-cols-1 gap-6 md:grid-cols-3">
        {HIGHLIGHTS.map((item) => {
          const Icon = item.icon;
          return (
            <div
              key={item.title}
              className="rounded-xl border border-slate-200 bg-white p-6 shadow-xs flex flex-col justify-between"
            >
              <div>
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100 text-slate-700 mb-4">
                  <Icon className="h-5 w-5" />
                </div>
                <h3 className="text-base font-bold text-slate-900">{item.title}</h3>
                <p className="mt-2 text-xs leading-relaxed text-slate-600">{item.desc}</p>
              </div>
            </div>
          );
        })}
      </section>
    </div>
  );
}
