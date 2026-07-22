/**
 * Thin fetch wrapper for talking to OUR backend (which is the only layer
 * that ever communicates with Shopify — the Shopify Storefront token never
 * reaches this app). All Shopify-backed data flows through /api/shopify/*.
 *
 * If a signed-in session exists (see src/services/auth/sessionToken.ts),
 * its access token is attached automatically as `Authorization: Bearer
 * <token>` to every request — repositories never need to think about this.
 * On a 401 (expired access token mid-session), one silent refresh-and-retry
 * is attempted transparently before surfacing an error.
 */
import { attemptSilentRefresh, getSessionAccessToken } from '@/src/services/auth/sessionToken';

const BASE_URL = `${process.env.EXPO_PUBLIC_BACKEND_URL}/api`;

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

function buildHeaders(extra?: Record<string, string>): Record<string, string> {
  const token = getSessionAccessToken();
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...extra,
  };
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      message = body.detail || message;
    } catch {
      // ignore body parse failure
    }
    throw new ApiError(message, response.status);
  }
  return response.json() as Promise<T>;
}

async function request<T>(path: string, init: RequestInit, allowRefreshRetry = true): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, init);
  if (response.status === 401 && allowRefreshRetry) {
    const newToken = await attemptSilentRefresh();
    if (newToken) {
      const retryHeaders = { ...(init.headers as Record<string, string>), Authorization: `Bearer ${newToken}` };
      return request<T>(path, { ...init, headers: retryHeaders }, false);
    }
  }
  return handleResponse<T>(response);
}

export const apiClient = {
  get: async <T>(path: string): Promise<T> => request<T>(path, { headers: buildHeaders() }),
  post: async <T>(path: string, body?: unknown): Promise<T> =>
    request<T>(path, { method: 'POST', headers: buildHeaders(), body: body ? JSON.stringify(body) : undefined }),
  put: async <T>(path: string, body?: unknown): Promise<T> =>
    request<T>(path, { method: 'PUT', headers: buildHeaders(), body: body ? JSON.stringify(body) : undefined }),
  delete: async <T>(path: string, body?: unknown): Promise<T> =>
    request<T>(path, { method: 'DELETE', headers: buildHeaders(), body: body ? JSON.stringify(body) : undefined }),
};
