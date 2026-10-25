import { lazy, Suspense, type ReactNode } from "react";
import { Navigate, createBrowserRouter } from "react-router-dom";
import type { Role } from "@/api/types";
import { AppLayout } from "@/components/layout/AppLayout";
import { useAuth } from "@/hooks/useAuth";
import ComingSoonPage from "@/pages/ComingSoonPage";
import NotificationsPage from "@/pages/NotificationsPage";
import LoginPage from "@/pages/auth/LoginPage";
import RegisterPage from "@/pages/auth/RegisterPage";
import {
  ForgotPasswordPage,
  MustChangePasswordPage,
  PendingPage,
  ResetPasswordPage,
} from "@/pages/auth/SimpleAuthPages";
import VerifyOtpPage from "@/pages/auth/VerifyOtpPage";
import DishesPage from "@/pages/chef/DishesPage";
import PlannerPage from "@/pages/chef/PlannerPage";
import HomePage from "@/pages/employee/HomePage";
import ReservationsPage from "@/pages/employee/ReservationsPage";
import AccountsPage from "@/pages/hr/AccountsPage";
import FinalizePage from "@/pages/management/FinalizePage";

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
      { path: "notifications", element: <NotificationsPage /> },
      {
        path: "scan",
        element: <Protected roles={["scanner"]}><Suspense fallback={null}><ScanPage /></Suspense></Protected>,
      },
      {
        path: "chef/planner",
        element: <Protected roles={["chef"]}><PlannerPage /></Protected>,
      },
      {
        path: "chef/dishes",
        element: <Protected roles={["chef"]}><DishesPage /></Protected>,
      },
      {
        path: "management/finalize",
        element: <Protected roles={["management"]}><FinalizePage /></Protected>,
      },
      {
        path: "management/reports",
        element: <Protected roles={["management"]}><ComingSoonPage title="nav.reports" refs="FR-21, FR-23, FR-36" /></Protected>,
      },
      {
        path: "hr/accounts",
        element: <Protected roles={["hr"]}><AccountsPage /></Protected>,
      },
      {
        path: "hr/reports",
        element: <Protected roles={["hr"]}><ComingSoonPage title="nav.reports" refs="FR-22" /></Protected>,
      },
    ],
  },
  { path: "*", element: <Navigate to="/" replace /> },
]);
