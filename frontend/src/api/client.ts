/** Thin fetch wrapper: JSON, JWT access token, automatic refresh, typed errors. */

const BASE = "/api/v1";
const ACCESS = "canteen.access";
const REFRESH = "canteen.refresh";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public fields?: Record<string, string[]>,
  ) {
    super(message);
  }
}

function read(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

export const tokens = {
  get access() {
    return read(ACCESS);
  },
  set(access: string, refresh: string) {
    try {
      localStorage.setItem(ACCESS, access);
      localStorage.setItem(REFRESH, refresh);
    } catch {
      /* private mode: session-only */
    }
  },
  clear() {
    try {
      localStorage.removeItem(ACCESS);
      localStorage.removeItem(REFRESH);
    } catch {
      /* ignore */
    }
  },
};

async function refreshAccess(): Promise<boolean> {
  const refresh = read(REFRESH);
  if (!refresh) return false;
  const res = await fetch(`${BASE}/auth/token/refresh/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh }),
  });
  if (!res.ok) return false;
  const data = await res.json();
  tokens.set(data.access, data.refresh ?? refresh);
  return true;
}

async function toError(res: Response): Promise<ApiError> {
  let body: Record<string, unknown> = {};
  try {
    body = await res.json();
  } catch {
    /* not JSON */
  }
  const code = typeof body.code === "string" ? body.code : `http_${res.status}`;
  const detail = typeof body.detail === "string" ? body.detail : code;
  const fields = body.code ? undefined : (body as Record<string, string[]>);
  return new ApiError(res.status, code, detail, fields);
}

export async function api<T>(path: string, options: RequestInit & { json?: unknown } = {}, retry = true): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.json !== undefined) headers.set("Content-Type", "application/json");
  if (tokens.access) headers.set("Authorization", `Bearer ${tokens.access}`);
  headers.set("Accept-Language", document.documentElement.lang || "fr");

  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers,
    body: options.json !== undefined ? JSON.stringify(options.json) : options.body,
  });

  if (res.status === 401 && retry && (await refreshAccess())) return api<T>(path, options, false);
  if (!res.ok) throw await toError(res);
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}
