import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'sonner';
import { lazy, Suspense } from 'react';
import { ErrorBoundary } from '@/components/common/ErrorBoundary';
import { ProtectedRoute } from '@/components/common/ProtectedRoute';
import { Layout } from '@/components/layout/Layout';
import { Loading } from '@/components/common/Loading';
import { OfflineBanner } from '@/components/common/OfflineBanner';
import { SkipLink } from '@/components/common/SkipLink';
import { Login } from '@/pages/Login';
import { ROUTES } from '@/utils/constants';
import { handleError } from '@/utils/errorHandler';
import '@/styles/globals.css';

// Lazy load pages for code splitting
const Dashboard = lazy(() => import('@/pages/Dashboard'));
const Users = lazy(() => import('@/pages/Users'));
const Settings = lazy(() => import('@/pages/Settings'));
const Logs = lazy(() => import('@/pages/Logs'));
const AppointmentRequest = lazy(() => import('@/pages/AppointmentRequest'));
const AuditLogs = lazy(() => import('@/pages/AuditLogs'));
const SystemHealth = lazy(() => import('@/pages/SystemHealth'));
const NotFound = lazy(() => import('@/pages/NotFound'));

// Create a client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (failureCount, error) => {
        // Don't retry on 401/403 errors
        // Check both error message and response status if available
        const errorMessage = error instanceof Error ? error.message : '';
        const isAuthError = errorMessage.includes('401') || errorMessage.includes('403');
        
        if (isAuthError) {
          return false;
        }
        return failureCount < 2;
      },
      refetchOnWindowFocus: false,
      staleTime: 30000, // 30 seconds default
    },
    mutations: {
      onError: (error) => {
        // Global mutation error handler
        handleError(error, { showToast: true });
      },
    },
  },
});

function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <SkipLink />
          <OfflineBanner />
          <Suspense fallback={<Loading fullScreen text="Yükleniyor..." />}>
            <Routes>
              {/* Public routes */}
              <Route path={ROUTES.LOGIN} element={<Login />} />

              {/* Protected routes */}
              <Route
                element={
                  <ProtectedRoute>
                    <Layout />
                  </ProtectedRoute>
                }
              >
                <Route path={ROUTES.DASHBOARD} element={<Dashboard />} />
                <Route path={ROUTES.USERS} element={<Users />} />
                <Route path={ROUTES.SETTINGS} element={<Settings />} />
                <Route path={ROUTES.LOGS} element={<Logs />} />
                <Route path={ROUTES.APPOINTMENTS} element={<AppointmentRequest />} />
                <Route path={ROUTES.AUDIT_LOGS} element={<AuditLogs />} />
                <Route path={ROUTES.SYSTEM_HEALTH} element={<SystemHealth />} />
              </Route>

              {/* 404 */}
              <Route path="/404" element={<NotFound />} />
              <Route path="*" element={<Navigate to="/404" replace />} />
            </Routes>
          </Suspense>
        </BrowserRouter>

        {/* Toast notifications */}
        <Toaster
          position="top-right"
          theme="dark"
          richColors
          closeButton
          toastOptions={{
            style: {
              background: 'rgba(30, 41, 59, 0.9)',
              backdropFilter: 'blur(12px)',
              border: '1px solid rgba(51, 65, 85, 0.5)',
            },
          }}
        />
      </QueryClientProvider>
    </ErrorBoundary>
  );
}

export default App;
