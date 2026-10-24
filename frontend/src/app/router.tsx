import { lazy, Suspense, type ReactNode } from "react";
import { Navigate, createBrowserRouter } from "react-router-dom";
import type { Role } from "@/api/types";
import { AppLayout } from "@/components/layout/AppLayout";
import { useAuth } from "@/hooks/useAuth";
import ComingSoonPage from "@/pages/ComingSoonPage";
import LoginPage from "@/pages/auth/LoginPage";
import RegisterPage from "@/pages/auth/RegisterPage";
import {
  ForgotPasswordPage,
  MustChangePasswordPage,
  PendingPage,
  ResetPasswordPage,
} from "@/pages/auth/SimpleAuthPages";
import VerifyOtpPage from "@/pages/auth/VerifyOtpPage";
import HomePage from "@/pages/employee/HomePage";
import ReservationsPage from "@/pages/employee/ReservationsPage";

// The camera library is heavy: load the scanner screen only on the canteen phone.
const ScanPage = lazy(() => import("@/pages/scanner/ScanPage"));

/** Route guard: must be logged in, optionally with one of the given roles (admin always passes). */
function Protected({ roles, children }: { roles?: Role[]; children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (!user) return <Navigate to="/login" replace />;
  if (user.must_change_password) return <Navigate to="/change-password" replace />;
  if (roles && !roles.includes(user.role) && user.role !== "admin") return <Navigate to="/" replace />;
  return <>{children}</>;
}

export const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  { path: "/register", element: <RegisterPage /> },
  { path: "/verify", element: <VerifyOtpPage /> },
  { path: "/pending", element: <PendingPage /> },
  { path: "/forgot-password", element: <ForgotPasswordPage /> },
  { path: "/reset-password", element: <ResetPasswordPage /> },
  { path: "/change-password", element: <MustChangePasswordPage /> },
  {
    element: (
      <Protected>
        <AppLayout />
      </Protected>
    ),
    children: [
      { index: true, element: <HomePage /> },
      { path: "reservations", element: <ReservationsPage /> },
      {
        path: "scan",
        element: <Protected roles={["scanner"]}><Suspense fallback={null}><ScanPage /></Suspense></Protected>,
      },
      {
        path: "chef/planner",
        element: <Protected roles={["chef"]}><ComingSoonPage title="nav.planner" refs="FR-07, FR-09, FR-10, FR-38" /></Protected>,
      },
      {
        path: "chef/dishes",
        element: <Protected roles={["chef"]}><ComingSoonPage title="nav.dishes" refs="FR-29 – FR-31" /></Protected>,
      },
      {
        path: "management/finalize",
        element: <Protected roles={["management"]}><ComingSoonPage title="nav.finalize" refs="FR-24 – FR-28, FR-32" /></Protected>,
      },
      {
        path: "management/reports",
        element: <Protected roles={["management"]}><ComingSoonPage title="nav.reports" refs="FR-21, FR-23, FR-36" /></Protected>,
      },
      {
        path: "hr/accounts",
        element: <Protected roles={["hr"]}><ComingSoonPage title="nav.accounts" refs="FR-04 – FR-06, FR-37, FR-40" /></Protected>,
      },
      {
        path: "hr/reports",
        element: <Protected roles={["hr"]}><ComingSoonPage title="nav.reports" refs="FR-22" /></Protected>,
      },
    ],
  },
  { path: "*", element: <Navigate to="/" replace /> },
]);
