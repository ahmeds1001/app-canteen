/** One function per backend endpoint, grouped by domain. Pages never call `api()` directly. */
import { api } from "./client";
import type {
  AuthTokens,
  Dish,
  FinalizationProposal,
  Health,
  ManagedUser,
  Menu,
  NotificationList,
  PublicSettings,
  Reservation,
  Role,
  ScanResult,
  StaffMenu,
  User,
} from "./types";

export const settingsApi = {
  public: () => api<PublicSettings>("/settings/public/"),
  health: () => api<Health>("/health/"),
};

export const authApi = {
  register: (data: {
    first_name: string;
    last_name: string;
    work_email: string;
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

/** HR dashboard (FR-04 to FR-06, FR-40). */
export const userAdminApi = {
  list: (filters: { status?: string; q?: string } = {}) => {
    const q = new URLSearchParams();
    if (filters.status) q.set("status", filters.status);
    if (filters.q) q.set("q", filters.q);
    return api<ManagedUser[]>(`/auth/users/?${q}`);
  },
  /** HR types the employee's matricule when approving. */
  approve: (id: number, employee_number: string) =>
    api<ManagedUser>(`/auth/users/${id}/approve/`, { method: "POST", json: { employee_number } }),
  setEmployeeNumber: (id: number, employee_number: string) =>
    api<ManagedUser>(`/auth/users/${id}/employee-number/`, { method: "POST", json: { employee_number } }),
  reject: (id: number, reason: string) =>
    api<ManagedUser>(`/auth/users/${id}/reject/`, { method: "POST", json: { reason } }),
  /** FR-41: admin only. */
  setRole: (id: number, role: Role) =>
    api<ManagedUser>(`/auth/users/${id}/role/`, { method: "POST", json: { role } }),
  changeStatus: (id: number, transition: "suspend" | "reactivate" | "deactivate") =>
    api<ManagedUser>(`/auth/users/${id}/status/${transition}/`, { method: "POST" }),
  resetPassword: (id: number) =>
    api<{ temporary_password: string; expires_in_hours: number }>(`/auth/users/${id}/reset-password/`, {
      method: "POST",
    }),
};

export type DishInput = {
  name: string;
  description: string;
  category: string;
  allergens: string;
  photo?: File | null;
};

/** JSON when there is no new photo, multipart when one is uploaded. */
function dishBody(data: Partial<DishInput>): { json?: unknown; body?: FormData } {
  const { photo, ...fields } = data;
  if (!photo) return { json: fields };
  const body = new FormData();
  Object.entries(fields).forEach(([k, v]) => body.append(k, String(v ?? "")));
  body.append("photo", photo);
  return { body };
}

/** Chef's dish library (FR-29 to FR-31). */
export const dishApi = {
  list: (filters: { q?: string; category?: string; archived?: boolean } = {}) => {
    const q = new URLSearchParams();
    if (filters.q) q.set("q", filters.q);
    if (filters.category) q.set("category", filters.category);
    if (filters.archived) q.set("archived", "1");
    return api<Dish[]>(`/dishes/?${q}`);
  },
  create: (data: DishInput) => api<Dish>("/dishes/", { method: "POST", ...dishBody(data) }),
  update: (id: number, data: Partial<DishInput>) =>
    api<Dish>(`/dishes/${id}/`, { method: "PATCH", ...dishBody(data) }),
  archive: (id: number) => api<Dish>(`/dishes/${id}/archive/`, { method: "POST" }),
};

export const menuApi = {
  list: (from?: string, to?: string) => {
    const q = new URLSearchParams();
    if (from) q.set("from", from);
    if (to) q.set("to", to);
    return api<Menu[]>(`/menus/?${q}`);
  },
  /** Same endpoint; chef / management / admin get the staff fields. */
  staffList: (from: string, to: string) => api<StaffMenu[]>(`/menus/?from=${from}&to=${to}`),
  create: (date: string) => api<StaffMenu>("/menus/", { method: "POST", json: { date } }),
  setItems: (date: string, dish_ids: number[]) =>
    api<StaffMenu>(`/menus/${date}/items/`, { method: "PUT", json: { dish_ids } }),
  publish: (date: string) => api<StaffMenu>(`/menus/${date}/publish/`, { method: "POST" }),
  close: (date: string, reason: string) =>
    api<StaffMenu>(`/menus/${date}/close/`, { method: "POST", json: { reason } }),
  finalization: (date: string) => api<FinalizationProposal>(`/menus/${date}/finalization/`),
  finalize: (date: string, final_plate_count: number) =>
    api<StaffMenu>(`/menus/${date}/finalize/`, { method: "POST", json: { final_plate_count } }),
};

/** In-app notifications and phone push (spec §8). */
export const notificationApi = {
  list: () => api<NotificationList>("/notifications/"),
  read: (id: number) => api<{ unread: number }>(`/notifications/${id}/read/`, { method: "POST" }),
  readAll: () => api<{ unread: number }>("/notifications/read-all/", { method: "POST" }),
  setEveningReminder: (evening_reminder: boolean) =>
    api<{ evening_reminder: boolean }>("/notifications/preferences/", { method: "PATCH", json: { evening_reminder } }),
};

export const pushApi = {
  key: () => api<{ enabled: boolean; public_key: string }>("/notifications/push/key/"),
  subscribe: (subscription: PushSubscriptionJSON) =>
    api<void>("/notifications/push/subscribe/", { method: "POST", json: subscription }),
  unsubscribe: (endpoint: string) =>
    api<void>("/notifications/push/unsubscribe/", { method: "POST", json: { endpoint } }),
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
