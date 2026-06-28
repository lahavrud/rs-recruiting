import { Suspense, useEffect } from "react";

import { HelmetProvider } from "react-helmet-async";
import { BrowserRouter, Routes, Route, useLocation } from "react-router-dom";

import AdminRoute from "@/components/guards/AdminRoute";
import CandidateRoute from "@/components/guards/CandidateRoute";
import CompanyRoute from "@/components/guards/CompanyRoute";
import ProtectedRoute from "@/components/guards/ProtectedRoute";
import AppShell from "@/components/layout/AppShell";
import CookieConsent from "@/components/ui/CookieConsent";
import RouteErrorBoundary from "@/components/ui/RouteErrorBoundary";
import { AuthProvider } from "@/contexts/AuthContext";
// Eager — entry funnels Google + direct visits land on most often. Keeping
// these in the main bundle is critical for LCP / Core Web Vitals on the
// pages that receive organic search traffic.
import LoginPage from "@/pages/LoginPage";
import JobBoardPage from "@/pages/public/JobBoardPage";
import JobDetailPage from "@/pages/public/JobDetailPage";
import LandingPage from "@/pages/public/LandingPage";
import { lazyWithRetry } from "@/utils/lazyWithRetry";

// Lazy — secondary public pages + every behind-auth screen. Chunked out so
// they don't bloat the initial download for a visitor landing on / or /jobs.
// `lazyWithRetry` recovers gracefully from a stale-chunk crash when a deploy
// happens while a user has the SPA open (their tab's bundle references chunk
// hashes that no longer exist on the server).
const ApplicationPage = lazyWithRetry(() => import("@/pages/public/ApplicationPage"));
const AboutPage = lazyWithRetry(() => import("@/pages/public/AboutPage"));
const ContactPage = lazyWithRetry(() => import("@/pages/public/ContactPage"));
const PrivacyPolicyPage = lazyWithRetry(
  () => import("@/pages/public/PrivacyPolicyPage"),
);
const TermsPage = lazyWithRetry(() => import("@/pages/public/TermsPage"));
const ArticlesIndexPage = lazyWithRetry(
  () => import("@/pages/public/ArticlesIndexPage"),
);
const ArticlePage = lazyWithRetry(() => import("@/pages/public/ArticlePage"));
const RegisterPage = lazyWithRetry(() => import("@/pages/RegisterPage"));
const RegisterCandidatePage = lazyWithRetry(
  () => import("@/pages/RegisterCandidatePage"),
);
const ActivatePage = lazyWithRetry(() => import("@/pages/ActivatePage"));
const ForgotPasswordPage = lazyWithRetry(() => import("@/pages/ForgotPasswordPage"));
const ResetPasswordPage = lazyWithRetry(() => import("@/pages/ResetPasswordPage"));
const DashboardPage = lazyWithRetry(() => import("@/pages/DashboardPage"));
const NotFoundPage = lazyWithRetry(() => import("@/pages/NotFoundPage"));
const AdminCompaniesPage = lazyWithRetry(
  () => import("@/pages/admin/AdminCompaniesPage"),
);
const AdminJobsPage = lazyWithRetry(() => import("@/pages/admin/AdminJobsPage"));
const AdminApplicationsPage = lazyWithRetry(
  () => import("@/pages/admin/AdminApplicationsPage"),
);
const AdminApplicationsTriagePage = lazyWithRetry(
  () => import("@/pages/admin/AdminApplicationsTriagePage"),
);
const AdminReviewQueuePage = lazyWithRetry(
  () => import("@/pages/admin/AdminReviewQueuePage"),
);
const AdminCandidatesPage = lazyWithRetry(
  () => import("@/pages/admin/AdminCandidatesPage"),
);
const AdminProfilePage = lazyWithRetry(
  () => import("@/pages/admin/AdminProfilePage"),
);
const CompanyJobsPage = lazyWithRetry(() => import("@/pages/company/CompanyJobsPage"));
const CompanyPostJobPage = lazyWithRetry(() => import("@/pages/company/CompanyPostJobPage"));
const CompanyEditJobPage = lazyWithRetry(() => import("@/pages/company/CompanyEditJobPage"));
const CompanyJobKanbanPage = lazyWithRetry(
  () => import("@/pages/company/CompanyJobKanbanPage"),
);
const CompanyProfilePage = lazyWithRetry(
  () => import("@/pages/company/CompanyProfilePage"),
);
const CandidateProfilePage = lazyWithRetry(
  () => import("@/pages/candidate/CandidateProfilePage"),
);
const CandidateApplicationsPage = lazyWithRetry(
  () => import("@/pages/candidate/CandidateApplicationsPage"),
);
const CandidateApplicationDetailPage = lazyWithRetry(
  () => import("@/pages/candidate/CandidateApplicationDetailPage"),
);

function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);
  return null;
}

/** Push a page_view event to GTM's dataLayer on every SPA route change.
 *  GTM only fires once on initial load by default — without this, every
 *  client-side navigation would be invisible to GA4 / Tag Manager.
 *  No-ops when dataLayer isn't present (dev build with no VITE_GTM_ID). */
function GtmPageView() {
  const { pathname } = useLocation();
  useEffect(() => {
    const dl = (window as unknown as { dataLayer?: unknown[] }).dataLayer;
    if (Array.isArray(dl)) {
      dl.push({ event: "page_view", page_path: pathname });
    }
  }, [pathname]);
  return null;
}

/** Minimal placeholder while a lazy route chunk loads. Matches the dark
 *  page background so there's no light-flash, and shows a subtle copper
 *  ring so the user knows something is happening. */
function RouteFallback() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-page">
      <div
        className="h-9 w-9 animate-spin rounded-full border-2 border-copper/30 border-t-copper"
        role="status"
        aria-label="טוען…"
      />
    </div>
  );
}

export default function App() {
  return (
    <HelmetProvider>
      <BrowserRouter>
        <ScrollToTop />
        <GtmPageView />
        <CookieConsent />
        <AuthProvider>
          <AppShell>
            <Suspense fallback={<RouteFallback />}>
              <Routes>
                <Route path="/login" element={<LoginPage />} />
                <Route path="/register" element={<RegisterPage />} />
                <Route path="/register-candidate" element={<RegisterCandidatePage />} />
                <Route path="/activate" element={<ActivatePage />} />
                <Route path="/forgot-password" element={<ForgotPasswordPage />} />
                <Route path="/reset-password" element={<ResetPasswordPage />} />

                {/* Public landing page */}
                <Route path="/" element={<LandingPage />} />

                {/* Public informational pages */}
                <Route path="/privacy-policy" element={<PrivacyPolicyPage />} />
                <Route path="/terms" element={<TermsPage />} />
                <Route path="/about" element={<AboutPage />} />
                <Route path="/contact" element={<ContactPage />} />

                {/* Public job board */}
                <Route path="/jobs" element={<JobBoardPage />} />
                <Route
                  path="/jobs/:id"
                  element={
                    <RouteErrorBoundary>
                      <JobDetailPage />
                    </RouteErrorBoundary>
                  }
                />
                <Route
                  path="/jobs/:id/apply"
                  element={
                    <RouteErrorBoundary>
                      <ApplicationPage />
                    </RouteErrorBoundary>
                  }
                />

                {/* Public articles */}
                <Route path="/articles" element={<ArticlesIndexPage />} />
                <Route
                  path="/articles/:slug"
                  element={
                    <RouteErrorBoundary>
                      <ArticlePage />
                    </RouteErrorBoundary>
                  }
                />

                {/* Shared authenticated dashboard */}
                <Route
                  path="/dashboard"
                  element={
                    <ProtectedRoute>
                      <DashboardPage />
                    </ProtectedRoute>
                  }
                />

                {/* Admin-only routes */}
                <Route
                  path="/admin/companies"
                  element={
                    <AdminRoute>
                      <RouteErrorBoundary>
                        <AdminCompaniesPage />
                      </RouteErrorBoundary>
                    </AdminRoute>
                  }
                />
                <Route
                  path="/admin/companies/:id"
                  element={
                    <AdminRoute>
                      <RouteErrorBoundary>
                        <AdminCompaniesPage />
                      </RouteErrorBoundary>
                    </AdminRoute>
                  }
                />
                <Route
                  path="/admin/jobs"
                  element={
                    <AdminRoute>
                      <RouteErrorBoundary>
                        <AdminJobsPage />
                      </RouteErrorBoundary>
                    </AdminRoute>
                  }
                />
                <Route
                  path="/admin/jobs/:id"
                  element={
                    <AdminRoute>
                      <RouteErrorBoundary>
                        <AdminJobsPage />
                      </RouteErrorBoundary>
                    </AdminRoute>
                  }
                />
                <Route
                  path="/admin/applications"
                  element={
                    <AdminRoute>
                      <RouteErrorBoundary>
                        <AdminApplicationsPage />
                      </RouteErrorBoundary>
                    </AdminRoute>
                  }
                />
                <Route
                  path="/admin/applications/:id"
                  element={
                    <AdminRoute>
                      <RouteErrorBoundary>
                        <AdminApplicationsPage />
                      </RouteErrorBoundary>
                    </AdminRoute>
                  }
                />
                <Route
                  path="/admin/review"
                  element={
                    <AdminRoute>
                      <RouteErrorBoundary>
                        <AdminReviewQueuePage />
                      </RouteErrorBoundary>
                    </AdminRoute>
                  }
                />
                <Route
                  path="/admin/applications/triage"
                  element={
                    <AdminRoute>
                      <RouteErrorBoundary>
                        <AdminApplicationsTriagePage />
                      </RouteErrorBoundary>
                    </AdminRoute>
                  }
                />
                <Route
                  path="/admin/candidates"
                  element={
                    <AdminRoute>
                      <RouteErrorBoundary>
                        <AdminCandidatesPage />
                      </RouteErrorBoundary>
                    </AdminRoute>
                  }
                />
                <Route
                  path="/admin/candidates/:id"
                  element={
                    <AdminRoute>
                      <RouteErrorBoundary>
                        <AdminCandidatesPage />
                      </RouteErrorBoundary>
                    </AdminRoute>
                  }
                />
                <Route
                  path="/admin/profile"
                  element={
                    <AdminRoute>
                      <AdminProfilePage />
                    </AdminRoute>
                  }
                />

                {/* Company-only routes */}
                <Route
                  path="/company/jobs"
                  element={
                    <CompanyRoute>
                      <RouteErrorBoundary>
                        <CompanyJobsPage />
                      </RouteErrorBoundary>
                    </CompanyRoute>
                  }
                />
                <Route
                  path="/company/jobs/new"
                  element={
                    <CompanyRoute>
                      <RouteErrorBoundary>
                        <CompanyPostJobPage />
                      </RouteErrorBoundary>
                    </CompanyRoute>
                  }
                />
                <Route
                  path="/company/jobs/:jobId/edit"
                  element={
                    <CompanyRoute>
                      <RouteErrorBoundary>
                        <CompanyEditJobPage />
                      </RouteErrorBoundary>
                    </CompanyRoute>
                  }
                />
                <Route
                  path="/company/jobs/:jobId"
                  element={
                    <CompanyRoute>
                      <RouteErrorBoundary>
                        <CompanyJobKanbanPage />
                      </RouteErrorBoundary>
                    </CompanyRoute>
                  }
                />
                <Route
                  path="/company/profile"
                  element={
                    <CompanyRoute>
                      <RouteErrorBoundary>
                        <CompanyProfilePage />
                      </RouteErrorBoundary>
                    </CompanyRoute>
                  }
                />

                {/* Candidate-only routes (Sprint 11 / #608, #609) */}
                <Route
                  path="/candidate/profile"
                  element={
                    <CandidateRoute>
                      <RouteErrorBoundary>
                        <CandidateProfilePage />
                      </RouteErrorBoundary>
                    </CandidateRoute>
                  }
                />
                <Route
                  path="/candidate/applications"
                  element={
                    <CandidateRoute>
                      <RouteErrorBoundary>
                        <CandidateApplicationsPage />
                      </RouteErrorBoundary>
                    </CandidateRoute>
                  }
                />
                <Route
                  path="/candidate/applications/:id"
                  element={
                    <CandidateRoute>
                      <RouteErrorBoundary>
                        <CandidateApplicationDetailPage />
                      </RouteErrorBoundary>
                    </CandidateRoute>
                  }
                />

                {/* Catch-all */}
                <Route path="*" element={<NotFoundPage />} />
              </Routes>
            </Suspense>
          </AppShell>
        </AuthProvider>
      </BrowserRouter>
    </HelmetProvider>
  );
}
