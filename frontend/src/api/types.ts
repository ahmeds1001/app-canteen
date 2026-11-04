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
  /** Entered by HR at approval; null while the account is waiting. */
  employee_number: string | null;
  department: string;
  role: Role;
  status: AccountStatus;
  preferred_language: string;
  must_change_password: boolean;
  evening_reminder: boolean;
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
  /** The matter was dealt with (by this person or a colleague): shown as "already handled". */
  resolved_at: string | null;
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
  /** Reservations for day D close at `cutoff_time` on D - cutoff_days (0 = the same day). */
  cutoff_days: number;
  cutoff_time: string;
  service_window_start: string;
  service_window_end: string;
  /** Plate count locked (and auto-finalized if not confirmed) at this time on day D. */
  finalization_deadline: string;
  service_weekdays: string;
  publish_deadline_days: number;
  publish_deadline_time: string;
  payment_enabled: boolean;
  currency: string;
  default_language: string;
  enabled_languages: string;
}

/** Every parameter the admin edits on the Settings screen (FR-46). Times are "HH:MM:SS". */
export interface AdminSettings {
  service_weekdays: string;
  cutoff_days: number;
  cutoff_time: string;
  publish_deadline_days: number;
  publish_deadline_time: string;
  finalization_deadline: string;
  service_window_start: string;
  service_window_end: string;
  menu_missing_reminder_time: string;
  finalization_reminder_time: string;
  evening_reminder_time: string;
  buffer_mode: "percentage" | "fixed";
  buffer_value: number;
  kitchen_max_plates: number | null;
  booking_horizon_days: number | null;
  no_show_warning_threshold: number;
  no_show_grace_until: string | null;
  payment_enabled: boolean;
  meal_paid_default: boolean;
  meal_price_default: string;
  currency: string;
  updated_at: string;
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

/** A day offers menu 1, and optionally menu 2; each employee picks one (decided 2026-11-03). */
export type MenuChoice = 1 | 2;

export interface MenuItem {
  id: number;
  /** Which menu of the day this dish belongs to. */
  choice: MenuChoice;
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
  /** Menus offered that day: [1] or [1, 2]. */
  choices: MenuChoice[];
  /** One price for the day, the same for both menus; paid from the balance when reserving. */
  is_paid: boolean;
  price: string | null;
  reservation_cutoff: string;
  is_open_for_reservation: boolean;
}

/** Counts per menu, keyed "1" / "2". */
export type PerMenu = Partial<Record<"1" | "2", number>>;

/** Extra fields returned to chef / management / admin (MenuStaffSerializer). */
export interface StaffMenu extends Menu {
  reserved_count: number;
  reserved_by_choice: PerMenu;
  final_plate_count: number | null;
  final_plates_by_choice: PerMenu;
  buffer: number | null;
  auto_finalized: boolean;
  finalized_at: string | null;
  closed_reason: string;
}

export interface ChoiceProposal {
  choice: MenuChoice;
  reserved: number;
  buffer: number;
  proposed: number;
}

export interface FinalizationProposal {
  reserved: number;
  buffer: number;
  proposed: number;
  choices: ChoiceProposal[];
}

export type ReservationStatus = "reserved" | "cancelled" | "served" | "no_show";
/** Paid from the balance when reserving; refunded when cancelled in time. "unpaid" only exists in old rows. */
export type PaymentStatus = "not_required" | "unpaid" | "paid" | "refunded";

export interface Reservation {
  id: number;
  date: string;
  choice: MenuChoice;
  /** How many menus the day offers (the menu number is shown only when there are two). */
  menu_choices: number;
  status: ReservationStatus;
  reserved_at: string;
  served_at: string | null;
  payment_status: PaymentStatus;
  amount_due: string | null;
  qr_payload: string | null;
  /** Dishes of the chosen menu. */
  menu_items: string[];
}

export interface ScanResult {
  id: number;
  date: string;
  status: ReservationStatus;
  full_name: string;
  employee_number: string;
  /** Which plate to serve. */
  choice: MenuChoice;
  menu_items: string[];
  payment_status: PaymentStatus;
  amount_due: string | null;
  served_at: string | null;
}

/** A row of a day's reservation list (scanner and management). */
export interface DayReservation extends ScanResult {
  department: string;
  reserved_at: string;
  cancelled_at: string | null;
  scan_method: "qr" | "manual" | "";
}

/** Cash received on one day (FR-45): the scanner's own top-ups today, or every cashier for management. */
export interface CashReport {
  date: string;
  scope: "mine" | "all";
  topups: { count: number; total: string };
  corrections: { count: number; total: string };
  total: string;
  cashiers: { id: number | null; name: string; count: number; total: string }[];
  rows: {
    id: number;
    at: string;
    kind: "topup" | "correction";
    amount: string;
    employee: string;
    employee_number: string | null;
    by: string;
    note: string;
  }[];
}

export interface DayList {
  date: string;
  menu: null | {
    status: MenuStatus;
    is_placeholder: boolean;
    price: string | null;
    final_plate_count: number | null;
    final_plates_by_choice: PerMenu;
    choices: { choice: MenuChoice; dishes: string[]; reserved: number }[];
  };
  counts: Record<ReservationStatus | "total", number>;
  rows: DayReservation[];
}

/** Management dashboard: one employee's month. `pending` = reserved, day not over yet (not an absence). */
export interface AttendanceRow {
  user_id: number;
  name: string;
  employee_number: string | null;
  department: string;
  status: AccountStatus;
  reserved: number;
  served: number;
  no_show: number;
  pending: number;
  cancelled: number;
  menu_1: number;
  menu_2: number;
  /** Absences / (served + absences), 0 to 1. */
  no_show_rate: number;
  /** TND paid from the balance for that month's meals. */
  spent: string;
  /** Reached the monthly no-show warning threshold (3 by default). */
  over_threshold: boolean;
}

export interface MonthlyAttendance {
  month: string;
  threshold: number;
  departments: string[];
  totals: Omit<AttendanceRow, "user_id" | "name" | "employee_number" | "department" | "status" | "over_threshold"> & {
    employees: number;
    eating: number;
    over_threshold: number;
  };
  rows: AttendanceRow[];
}

export interface EmployeeMonth {
  name: string;
  employee_number: string | null;
  rows: DayReservation[];
}

/** Prepaid balance (decided 2026-11-03). Amounts are TND strings with 3 decimals. */
export type TransactionKind = "topup" | "meal" | "refund" | "correction";

export interface BalanceTransaction {
  id: number;
  kind: TransactionKind;
  amount: string;
  balance_after: string;
  meal_date: string | null;
  note: string;
  by_name: string;
  created_at: string;
}

export interface MyBalance {
  balance: string;
  transactions: BalanceTransaction[];
}

/** An account as the cashier (scanner / management) sees it. */
export interface WalletAccount {
  id: number;
  full_name: string;
  employee_number: string | null;
  department: string;
  balance: string;
}
