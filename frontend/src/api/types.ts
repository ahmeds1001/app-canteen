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
  on_roster: boolean | null;
}

export interface AuthTokens {
  access: string;
  refresh: string;
  user: User;
}

export type MenuStatus = "draft" | "published" | "locked" | "finalized" | "closed";

export interface MenuItem {
  id: number;
  dish: number | null;
  name: string;
  description: string;
  category: "starter" | "main" | "dessert" | "side" | "drink";
  allergens: string;
  photo: string;
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
