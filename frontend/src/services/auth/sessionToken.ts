/**
 * Lightweight, module-level (non-React) home for the CURRENT session's
 * access token, so the plain-function apiClient/repositories can attach it
 * without needing to be React components. AuthContext is the only writer
 * (via setSessionAccessToken); everything else only reads.
 *
 * Also hosts a single "refresh handler" hook that AuthContext registers on
 * mount, so apiClient can transparently retry a request exactly once after
 * a silent session refresh if it ever gets a 401 mid-session.
 */
type RefreshHandler = () => Promise<string | null>;

let accessToken: string | null = null;
let refreshHandler: RefreshHandler | null = null;
// Single-flight guard: if multiple requests hit a 401 at nearly the same
// moment (e.g. several screens refetching after the app returns from
// background), each would otherwise call the backend's one-time-use
// refresh-token rotation independently — the second call finds the token
// already rotated/revoked and signs the user out. Sharing one in-flight
// promise means every concurrent caller awaits the SAME refresh attempt.
let inFlightRefresh: Promise<string | null> | null = null;

export function setSessionAccessToken(token: string | null): void {
  accessToken = token;
}

export function getSessionAccessToken(): string | null {
  return accessToken;
}

export function registerRefreshHandler(handler: RefreshHandler | null): void {
  refreshHandler = handler;
}

export async function attemptSilentRefresh(): Promise<string | null> {
  if (!refreshHandler) return null;
  if (inFlightRefresh) return inFlightRefresh;
  inFlightRefresh = refreshHandler().finally(() => {
    inFlightRefresh = null;
  });
  return inFlightRefresh;
}
