import { useEffect, useState } from 'react';
import {
  Activity,
  BarChart3,
  Clock,
  Compass,
  FileText,
  Layers,
  LogOut,
  Smartphone,
  TrendingUp,
  Users,
} from 'lucide-react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { getAnalytics } from '../api/analytics';
import { extractApiError } from '../api/client';
import KpiCard from '../components/dashboard/KpiCard';
import StatusBanner, { SkeletonCard, SkeletonChart } from '../components/layout/StatusBanner';
import { useJob } from '../hooks/useJob';
import { formatDuration, formatNumber } from '../utils/formatters';

const CHART_PALETTE = ['#4f46e5', '#06b6d4', '#10b981', '#f59e0b', '#ec4899', '#8b5cf6', '#64748b'];

export default function Dashboard() {
  const { jobId, filename, analytics: cachedAnalytics, updateJob } = useJob();
  const [analytics, setAnalytics] = useState(cachedAnalytics);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const fetchAnalytics = () => {
    if (!jobId) return;
    setLoading(true);
    setError('');
    getAnalytics(jobId)
      .then((data) => {
        const result = data.analytics || {};
        setAnalytics(result);
        updateJob({ analytics: result });
      })
      .catch((err) => {
        setError(extractApiError(err, 'Unable to load behavioral analytics metrics.'));
      })
      .finally(() => {
        setLoading(false);
      });
  };

  useEffect(() => {
    if (!jobId || analytics) return;
    fetchAnalytics();
  }, [jobId]);

  if (loading) {
    return (
      <div className="space-y-6">
        <StatusBanner type="loading" message="Loading BI dashboard metrics &amp; distributions..." />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </div>
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <SkeletonChart />
          <SkeletonChart />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <StatusBanner
        type="error"
        message={error}
        onRetry={fetchAnalytics}
      />
    );
  }

  if (!analytics) {
    return (
      <StatusBanner
        type="info"
        message="Analytics are not calculated yet. Please run session analysis from the Data Quality page."
      />
    );
  }

  const trafficByHour = (analytics.traffic_by_hour || []).map((item) => ({
    hour: `${String(item.hour).padStart(2, '0')}:00`,
    events: item.events,
  }));

  const trafficByDay = analytics.traffic_by_day || [];

  const actionDistribution = Object.entries(analytics.action_counts || {}).map(([action, count]) => ({
    action,
    count,
  }));

  const deviceDistribution = Object.entries(analytics.device_counts || {}).map(([device, count]) => ({
    device,
    count,
  }));

  const mostVisitedPages = (analytics.most_visited_pages || []).slice(0, 8).map((p) => ({
    page_url: p.page_url,
    visits: p.visits,
  }));

  const leastVisitedPages = (analytics.least_visited_pages || []).slice(0, 8).map((p) => ({
    page_url: p.page_url,
    visits: p.visits,
  }));

  const entryPages = Object.entries(analytics.entry_pages || {})
    .slice(0, 6)
    .map(([page, sessions]) => ({ page, sessions }));

  const exitPages = Object.entries(analytics.exit_pages || {})
    .slice(0, 6)
    .map(([page, sessions]) => ({ page, sessions }));

  return (
    <div className="space-y-8">
      {/* Dashboard Executive Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-indigo-600">
            <BarChart3 className="h-4 w-4" />
            Executive BI Dashboard
          </div>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
            Behavioral Analytics Overview
          </h1>
          <p className="mt-1 text-xs text-slate-500">
            Computed from dataset: <span className="font-semibold text-slate-700">{filename || jobId}</span>
          </p>
        </div>

        <div className="flex items-center gap-2 text-xs font-medium text-slate-500 bg-white border border-slate-200 rounded-xl px-3.5 py-2 shadow-2xs self-start sm:self-auto">
          <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
          <span>Calculated &amp; Persisted</span>
        </div>
      </div>

      {/* KPI Cards Row */}
      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <KpiCard
          label="Total Users"
          value={formatNumber(analytics.total_users)}
          subtitle="Distinct visitors"
          icon={Users}
        />
        <KpiCard
          label="Total Sessions"
          value={formatNumber(analytics.total_sessions)}
          subtitle="30m timeout window"
          icon={Clock}
        />
        <KpiCard
          label="Total Events"
          value={formatNumber(analytics.total_events)}
          subtitle="Recorded actions"
          icon={Activity}
        />
        <KpiCard
          label="Avg Session Duration"
          value={formatDuration(analytics.average_session_duration)}
          subtitle={`${Number(analytics.average_session_duration || 0).toFixed(1)}s average`}
          icon={Clock}
        />
        <KpiCard
          label="Avg Pages / Session"
          value={Number(analytics.average_pages_per_session || 0).toFixed(1)}
          subtitle={`${Number(analytics.average_events_per_session || 0).toFixed(1)} events / session`}
          icon={Layers}
        />
      </section>

      {/* Traffic Analysis Section */}
      <section className="space-y-4">
        <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-500">
          <TrendingUp className="h-4 w-4 text-indigo-600" />
          Traffic Cycles &amp; Volume Trends
        </div>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {/* Traffic by Hour */}
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-sm font-bold text-slate-900">Traffic by Hour (24h Distribution)</h2>
                <p className="text-xs text-slate-500">
                  Hourly event frequency across the day
                  {analytics.peak_traffic_hour !== null && (
                    <span className="font-semibold text-indigo-600 ml-1">
                      (Peak at {String(analytics.peak_traffic_hour).padStart(2, '0')}:00)
                    </span>
                  )}
                </p>
              </div>
            </div>
            <div className="h-68">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={trafficByHour}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                  <XAxis dataKey="hour" tick={{ fontSize: 11, fill: '#64748b' }} interval={2} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: '#64748b' }} />
                  <Tooltip
                    contentStyle={{ borderRadius: '8px', border: '1px solid #e2e8f0', fontSize: '12px' }}
                  />
                  <Bar dataKey="events" fill="#4f46e5" radius={[4, 4, 0, 0]} name="Events" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Traffic by Day */}
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-sm font-bold text-slate-900">Traffic by Day</h2>
                <p className="text-xs text-slate-500">Chronological daily volume progression</p>
              </div>
            </div>
            <div className="h-68">
              {trafficByDay.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={trafficByDay}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                    <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#64748b' }} />
                    <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: '#64748b' }} />
                    <Tooltip
                      contentStyle={{ borderRadius: '8px', border: '1px solid #e2e8f0', fontSize: '12px' }}
                    />
                    <Line
                      type="monotone"
                      dataKey="events"
                      stroke="#06b6d4"
                      strokeWidth={2.5}
                      dot={{ r: 3, fill: '#06b6d4' }}
                      name="Daily Events"
                    />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex h-full items-center justify-center text-xs text-slate-400">
                  Single-day or non-contiguous timestamp data
                </div>
              )}
            </div>
          </div>
        </div>
      </section>

      {/* User Behavior Section */}
      <section className="space-y-4">
        <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-500">
          <Users className="h-4 w-4 text-indigo-600" />
          User Behavior &amp; Client Distribution
        </div>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {/* Action Distribution */}
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs">
            <h2 className="text-sm font-bold text-slate-900">Action Distribution</h2>
            <p className="text-xs text-slate-500 mb-4">Normalized event actions across sessions</p>
            <div className="h-64">
              {actionDistribution.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={actionDistribution} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f1f5f9" />
                    <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11, fill: '#64748b' }} />
                    <YAxis dataKey="action" type="category" width={110} tick={{ fontSize: 11, fill: '#64748b' }} />
                    <Tooltip
                      contentStyle={{ borderRadius: '8px', border: '1px solid #e2e8f0', fontSize: '12px' }}
                    />
                    <Bar dataKey="count" fill="#10b981" radius={[0, 4, 4, 0]} name="Count" />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex h-full items-center justify-center text-xs text-slate-400">
                  No action counts recorded
                </div>
              )}
            </div>
          </div>

          {/* Device Distribution */}
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs">
            <h2 className="text-sm font-bold text-slate-900">Device Mix Distribution</h2>
            <p className="text-xs text-slate-500 mb-4">Breakdown of recorded activity by device</p>
            <div className="h-64 flex items-center justify-center">
              {deviceDistribution.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={deviceDistribution}
                      dataKey="count"
                      nameKey="device"
                      cx="50%"
                      cy="50%"
                      innerRadius={55}
                      outerRadius={85}
                      paddingAngle={3}
                    >
                      {deviceDistribution.map((entry, index) => (
                        <Cell
                          key={`cell-${entry.device}`}
                          fill={CHART_PALETTE[index % CHART_PALETTE.length]}
                        />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{ borderRadius: '8px', border: '1px solid #e2e8f0', fontSize: '12px' }}
                    />
                    <Legend
                      verticalAlign="bottom"
                      height={36}
                      formatter={(value) => <span className="text-xs text-slate-700 capitalize">{value}</span>}
                    />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <div className="text-xs text-slate-400">
                  Device column was not included in CSV mapping
                </div>
              )}
            </div>
          </div>
        </div>
      </section>

      {/* Content Analysis Section */}
      <section className="space-y-4">
        <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-500">
          <FileText className="h-4 w-4 text-indigo-600" />
          Content Popularity
        </div>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {/* Most Visited */}
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs">
            <h2 className="text-sm font-bold text-slate-900">Most Visited Pages</h2>
            <p className="text-xs text-slate-500 mb-4">Top web routes by page view volume</p>
            <div className="h-68">
              {mostVisitedPages.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={mostVisitedPages} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f1f5f9" />
                    <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11, fill: '#64748b' }} />
                    <YAxis dataKey="page_url" type="category" width={130} tick={{ fontSize: 11, fill: '#64748b' }} />
                    <Tooltip
                      contentStyle={{ borderRadius: '8px', border: '1px solid #e2e8f0', fontSize: '12px' }}
                    />
                    <Bar dataKey="visits" fill="#8b5cf6" radius={[0, 4, 4, 0]} name="Page Views" />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex h-full items-center justify-center text-xs text-slate-400">
                  No page view visits recorded
                </div>
              )}
            </div>
          </div>

          {/* Least Visited */}
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs">
            <h2 className="text-sm font-bold text-slate-900">Least Visited Pages</h2>
            <p className="text-xs text-slate-500 mb-4">Routes with the lowest recorded traffic</p>
            <div className="h-68">
              {leastVisitedPages.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={leastVisitedPages} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f1f5f9" />
                    <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11, fill: '#64748b' }} />
                    <YAxis dataKey="page_url" type="category" width={130} tick={{ fontSize: 11, fill: '#64748b' }} />
                    <Tooltip
                      contentStyle={{ borderRadius: '8px', border: '1px solid #e2e8f0', fontSize: '12px' }}
                    />
                    <Bar dataKey="visits" fill="#f59e0b" radius={[0, 4, 4, 0]} name="Page Views" />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex h-full items-center justify-center text-xs text-slate-400">
                  No least-visited pages recorded
                </div>
              )}
            </div>
          </div>
        </div>
      </section>

      {/* Navigation Boundaries Section */}
      <section className="space-y-4">
        <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-500">
          <Compass className="h-4 w-4 text-indigo-600" />
          Session Navigation Boundaries
        </div>

        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-emerald-700 mb-1">
              <Compass className="h-4 w-4" /> Entry Routes
            </div>
            <h3 className="text-sm font-bold text-slate-900">Top Session Entry Pages</h3>
            <p className="text-xs text-slate-500 mb-4">First page viewed at the start of a session</p>
            <div className="space-y-2">
              {entryPages.map((item, idx) => (
                <div
                  key={`entry-${idx}`}
                  className="flex items-center justify-between rounded-xl bg-slate-50 p-3 text-xs"
                >
                  <span className="font-mono font-semibold text-slate-800 truncate mr-2">
                    {item.page}
                  </span>
                  <span className="rounded-md bg-white border border-slate-200 px-2 py-0.5 font-bold text-slate-700 shrink-0">
                    {formatNumber(item.sessions)} sessions
                  </span>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-rose-700 mb-1">
              <LogOut className="h-4 w-4" /> Exit Routes
            </div>
            <h3 className="text-sm font-bold text-slate-900">Top Session Exit Pages</h3>
            <p className="text-xs text-slate-500 mb-4">Last page accessed before session termination</p>
            <div className="space-y-2">
              {exitPages.map((item, idx) => (
                <div
                  key={`exit-${idx}`}
                  className="flex items-center justify-between rounded-xl bg-slate-50 p-3 text-xs"
                >
                  <span className="font-mono font-semibold text-slate-800 truncate mr-2">
                    {item.page}
                  </span>
                  <span className="rounded-md bg-white border border-slate-200 px-2 py-0.5 font-bold text-slate-700 shrink-0">
                    {formatNumber(item.sessions)} sessions
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
