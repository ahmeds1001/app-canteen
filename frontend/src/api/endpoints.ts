/** One function per backend endpoint, grouped by domain. Pages never call `api()` directly. */
import { api } from "./client";
import type { AuthTokens, Menu, Reservation, ScanResult, User } from "./types";

export const authApi = {
  register: (data: {
    first_name: string;
    last_name: string;
    work_email: string;
    employee_number: string;
    department: string;
    password: string;
  }) => api<{ status: string; work_email: string }>("/auth/register/", { method: "POST", json: data }),
  verifyOtp: (work_email: string, code: string) =>
    api<{ status: string }>("/auth/otp/verify/", { method: "POST", json: { work_email, code } }),
  resendOtp: (work_email: string) => api("/auth/otp/resend/", { method: "POST", json: { work_email } }),
  login: (work_email: string, password: string) =>
    api<AuthTokens>("/auth/login/", { method: "POST", json: { work_email, password } }),
  me: () => api<User>("/auth/me/"),
  changePassword: (new_password: string) =>
    api<AuthTokens>("/auth/password/change/", { method: "POST", json: { new_password } }),
  forgotPassword: (work_email: string) => api("/auth/password/forgot/", { method: "POST", json: { work_email } }),
  resetPassword: (token: string, new_password: string) =>
    api("/auth/password/reset/", { method: "POST", json: { token, new_password } }),
};

export const menuApi = {
  list: (from?: string, to?: string) => {
    const q = new URLSearchParams();
    if (from) q.set("from", from);
    if (to) q.set("to", to);
    return api<Menu[]>(`/menus/?${q}`);
  },
};

export const reservationApi = {
  mine: (upcoming = true) => api<Reservation[]>(`/reservations/${upcoming ? "?upcoming=1" : ""}`),
  reserve: (date: string) => api<Reservation>("/reservations/", { method: "POST", json: { date } }),
  cancel: (id: number) => api<Reservation>(`/reservations/${id}/cancel/`, { method: "POST" }),
};

export const scanApi = {
  scan: (payload: string, scanned_at?: string) =>
    api<ScanResult>("/scan/", { method: "POST", json: { payload, scanned_at } }),
  search: (q: string) => api<ScanResult[]>(`/checkin/?q=${encodeURIComponent(q)}`),
  manual: (id: number) => api<ScanResult>(`/checkin/${id}/manual/`, { method: "POST" }),
  markPaid: (id: number) => api<ScanResult>(`/checkin/${id}/mark-paid/`, { method: "POST" }),
};
