/** API "models": mirror of the Django serializers (backend/apps/<app>/serializers.py). Keep them in sync. */

export type Role = "employee" | "hr" | "chef" | "scanner" | "management" | "admin";
export type AccountStatus =
  | "registered"
  | "email_verified"
  | "pending_hr"
  | "active"
  | "rejected"
  | "suspended"
  | "deactivated";

export interface User {
  id: number;
  first_name: string;
  last_name: string;
  full_name: string;
  work_email: string;
  employee_number: string;
  department: string;
  role: Role;
  status: AccountStatus;
  preferred_language: string;
  must_change_password: boolean;
  evening_reminder: boolean;
  on_roster: boolean | null;
}

/** In-app notification (spec §8). Title and body come translated from the server. */
export interface AppNotification {
  id: number;
  kind: string;
  title: string;
  body: string;
  link: string;
  created_at: string;
  read_at: string | null;
}

export interface NotificationList {
  unread: number;
  evening_reminder: boolean;
  results: AppNotification[];
}

export interface AuthTokens {
  access: string;
  refresh: string;
  user: User;
}

/** HR dashboard row (UserAdminViewSet). */
export interface ManagedUser extends User {
  created_at: string;
}

export interface Health {
  status: string;
  /** Company wall-clock time with offset, e.g. "2026-10-26T12:30:00+01:00". */
  server_time: string;
  /** True when a developer moved the clock with `manage.py dev_clock`. */
  clock_shifted: boolean;
}

export interface PublicSettings {
  cutoff_time: string;
  service_window_start: string;
  service_window_end: string;
  service_weekdays: string;
  publish_deadline_days: number;
  payment_enabled: boolean;
  currency: string;
  default_language: string;
  enabled_languages: string;
}

export type MenuStatus = "draft" | "published" | "locked" | "finalized" | "closed";
export type DishCategory = "starter" | "main" | "dessert" | "side" | "drink";
export const DISH_CATEGORIES: DishCategory[] = ["starter", "main", "side", "dessert", "drink"];

export interface Dish {
  id: number;
  name: string;
  description: string;
  category: DishCategory;
  allergens: string;
  photo: string | null;
  is_archived: boolean;
  last_served_on: string | null;
}

export interface MenuItem {
  id: number;
  dish: number | null;
  name: string;
  description: string;
  category: DishCategory;
  allergens: string;
  photo: string;
  /** Ready-to-use image address (/media/…) of the dish photo copied with the item, or null. */
  photo_url: string | null;
}

export interface Menu {
  id: number;
  date: string;
  status: MenuStatus;
  is_placeholder: boolean;
  items: MenuItem[];
  is_paid: boolean;
  price: string | null;
  reservation_cutoff: string;
  is_open_for_reservation: boolean;
}

/** Extra fields returned to chef / management / admin (MenuStaffSerializer). */
export interface StaffMenu extends Menu {
  reserved_count: number;
  final_plate_count: number | null;
  buffer: number | null;
  auto_finalized: boolean;
  finalized_at: string | null;
  closed_reason: string;
}

export interface FinalizationProposal {
  reserved: number;
  buffer: number;
  proposed: number;
}

export type ReservationStatus = "reserved" | "cancelled" | "served" | "no_show";
export type PaymentStatus = "not_required" | "unpaid" | "paid";

export interface Reservation {
  id: number;
  date: string;
  status: ReservationStatus;
  reserved_at: string;
  served_at: string | null;
  payment_status: PaymentStatus;
  amount_due: string | null;
  qr_payload: string | null;
  menu_items: string[];
}

export interface ScanResult {
  id: number;
  date: string;
  status: ReservationStatus;
  full_name: string;
  employee_number: string;
  payment_status: PaymentStatus;
  amount_due: string | null;
  served_at: string | null;
}
