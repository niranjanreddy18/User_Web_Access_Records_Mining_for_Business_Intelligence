import { BrowserRouter, Route, Routes } from 'react-router-dom';
import AppLayout from './components/layout/AppLayout';
import ProtectedRoute from './components/layout/ProtectedRoute';
import { JobProvider } from './hooks/useJob';
import Dashboard from './pages/Dashboard';
import Home from './pages/Home';
import Insights from './pages/Insights';
import Mapping from './pages/Mapping';
import Patterns from './pages/Patterns';
import QualityReport from './pages/QualityReport';
import Upload from './pages/Upload';

export default function App() {
  return (
    <JobProvider>
      <BrowserRouter>
        <AppLayout>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/upload" element={<Upload />} />
            <Route
              path="/mapping"
              element={
                <ProtectedRoute stepKey="mapping">
                  <Mapping />
                </ProtectedRoute>
              }
            />
            <Route
              path="/quality"
              element={
                <ProtectedRoute stepKey="quality">
                  <QualityReport />
                </ProtectedRoute>
              }
            />
            <Route
              path="/dashboard"
              element={
                <ProtectedRoute stepKey="dashboard">
                  <Dashboard />
                </ProtectedRoute>
              }
            />
            <Route
              path="/patterns"
              element={
                <ProtectedRoute stepKey="patterns">
                  <Patterns />
                </ProtectedRoute>
              }
            />
            <Route
              path="/insights"
              element={
                <ProtectedRoute stepKey="insights">
                  <Insights />
                </ProtectedRoute>
              }
            />
            <Route path="*" element={<Home />} />
          </Routes>
        </AppLayout>
      </BrowserRouter>
    </JobProvider>
  );
}
