/**
 * The HTTP client.
 *
 * Two things happen here that the rest of the app then never has to think
 * about: the access token is attached to every request, and a 401 triggers one
 * refresh attempt with all other in-flight requests queued behind it. Without
 * the queue, a screen that fires six requests on mount would fire six refreshes
 * and the token rotation would invalidate five of them.
 */
import axios, {
  AxiosError,
  type AxiosRequestConfig,
  type InternalAxiosRequestConfig,
} from "axios";

const ACCESS_KEY = "forge.access";
const REFRESH_KEY = "forge.refresh";

export const tokens = {
  get access() {
    return safeRead(ACCESS_KEY);
  },
  get refresh() {
    return safeRead(REFRESH_KEY);
  },
  set(access: string, refresh?: string) {
    safeWrite(ACCESS_KEY, access);
    if (refresh) safeWrite(REFRESH_KEY, refresh);
  },
  clear() {
    safeRemove(ACCESS_KEY);
    safeRemove(REFRESH_KEY);
  },
};

// localStorage throws in a private window with site data blocked, and the app
// should degrade to "signed out" rather than crash on load.
function safeRead(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}
function safeWrite(key: string, value: string) {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    /* session-only is an acceptable fallback */
  }
}
function safeRemove(key: string) {
  try {
    window.localStorage.removeItem(key);
  } catch {
    /* nothing to do */
  }
}

/**
 * Where the API lives.
 *
 * Empty in development, so requests go to `/api/v1` and Vite's proxy forwards
 * them — that keeps dev same-origin and means no CORS configuration is needed
 * to get started.
 *
 * In a built deployment the client and the API are on different hosts (Vercel
 * and forge-api.zafrika.com), so `VITE_API_BASE_URL` must be set at build
 * time. Vite inlines it, so changing it means rebuilding, not just restarting.
 *
 * The trailing slash is stripped because the paths below all begin with one,
 * and `//api/v1` is a 404 that takes a surprisingly long time to spot.
 */
const API_ORIGIN = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/+$/, "");

export const apiOrigin = API_ORIGIN;

export const api = axios.create({
  baseURL: `${API_ORIGIN}/api/v1`,
  headers: { "Content-Type": "application/json" },
  timeout: 20_000,
});

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = tokens.access;
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

let refreshing: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  const refresh = tokens.refresh;
  if (!refresh) return null;
  try {
    const { data } = await axios.post<{ access: string; refresh?: string }>(
      `${API_ORIGIN}/api/v1/accounts/token/refresh/`,
      { refresh },
      { headers: { "Content-Type": "application/json" } },
    );
    tokens.set(data.access, data.refresh);
    return data.access;
  } catch {
    tokens.clear();
    return null;
  }
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as (AxiosRequestConfig & { _retried?: boolean }) | undefined;

    const isAuthCall =
      original?.url?.includes("/accounts/token/") ||
      original?.url?.includes("/accounts/register/");

    if (error.response?.status === 401 && original && !original._retried && !isAuthCall) {
      original._retried = true;
      refreshing ??= refreshAccessToken().finally(() => {
        refreshing = null;
      });
      const token = await refreshing;
      if (token) {
        original.headers = { ...original.headers, Authorization: `Bearer ${token}` };
        return api.request(original);
      }
      window.dispatchEvent(new CustomEvent("forge:signed-out"));
    }
    return Promise.reject(error);
  },
);

/**
 * The API's error shape, flattened into something a form can use.
 *
 * Every endpoint returns `{"error": {"code", "detail"}}`, where detail is
 * either a sentence or a map of field errors. This turns both into one type so
 * that no component has to branch on which it got.
 */
export type ForgeError = {
  code: string;
  message: string;
  fieldErrors: Record<string, string>;
};

export function toForgeError(error: unknown): ForgeError {
  const fallback: ForgeError = {
    code: "unknown",
    message: "Something went wrong. Try again.",
    fieldErrors: {},
  };
  if (!axios.isAxiosError(error)) return fallback;

  if (error.code === "ECONNABORTED" || !error.response) {
    return {
      code: "network",
      message: "Could not reach FORGE. Check your connection and try again.",
      fieldErrors: {},
    };
  }

  const body = error.response.data as
    | { error?: { code?: string; detail?: unknown } }
    | undefined;
  const detail = body?.error?.detail;
  const code = body?.error?.code ?? "error";

  if (typeof detail === "string") return { code, message: detail, fieldErrors: {} };

  if (detail && typeof detail === "object") {
    const fieldErrors: Record<string, string> = {};
    for (const [key, value] of Object.entries(detail as Record<string, unknown>)) {
      fieldErrors[key] = Array.isArray(value) ? String(value[0]) : String(value);
    }
    // `__all__` and `detail` are whole-form problems, not field problems.
    const formMessage = fieldErrors.__all__ ?? fieldErrors.detail ?? "";
    delete fieldErrors.__all__;
    delete fieldErrors.detail;
    return {
      code,
      message: formMessage || "Please check the highlighted fields.",
      fieldErrors,
    };
  }
  return { ...fallback, code };
}
