import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { storage } from '@/src/utils/storage';
import { clearStoredDeliveryAddress } from '@/src/utils/storage/deliveryAddress';
import { authRepository } from '@/src/repositories';
import { attemptSilentRefresh, registerRefreshHandler, setSessionAccessToken } from '@/src/services/auth/sessionToken';
import { AuthSession, AuthUser } from '@/src/types';

const REFRESH_TOKEN_KEY = 'nowkart_refresh_token';

interface AuthContextValue {
  user: AuthUser | null;
  isAuthenticated: boolean;
  /** True only while restoring a session on cold start — guest browsing is
   * always available regardless of this flag. */
  isRestoring: boolean;
  applySession: (session: AuthSession) => Promise<void>;
  signOut: () => Promise<void>;
  refreshProfile: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

/**
 * Guest-first session management. The device only ever holds Now Kart's
 * own backend-issued { accessToken (short-lived JWT), refreshToken (opaque,
 * rotating) } pair via the shared `storage.secure*` helpers (Keychain /
 * EncryptedSharedPreferences on native, AsyncStorage on web where there is
 * no OS-level secure storage) — never a real Shopify Customer Account
 * token. Shopify token custody + refresh entirely lives server-side (see
 * /app/backend/auth/service.py).
 */
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isRestoring, setIsRestoring] = useState(true);
  const refreshTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const scheduleRefresh = useCallback((expiresInSeconds: number) => {
    if (refreshTimer.current) clearTimeout(refreshTimer.current);
    const delayMs = Math.max((expiresInSeconds - 60) * 1000, 10000);
    refreshTimer.current = setTimeout(() => {
      // Goes through the same single-flight guard as a reactive (401-
      // triggered) refresh, so a proactive timer firing at the same moment
      // as an in-flight API-triggered refresh never causes a double
      // rotation / spurious sign-out race.
      attemptSilentRefresh();
    }, delayMs);
  }, []);

  const applySession = useCallback(
    async (session: AuthSession) => {
      setSessionAccessToken(session.accessToken);
      await storage.secureSet(REFRESH_TOKEN_KEY, session.refreshToken);
      setUser(session.user);
      scheduleRefresh(session.expiresIn);
    },
    [scheduleRefresh]
  );

  const clearSession = useCallback(async () => {
    if (refreshTimer.current) clearTimeout(refreshTimer.current);
    setSessionAccessToken(null);
    setUser(null);
    await storage.secureRemove(REFRESH_TOKEN_KEY);
  }, []);

  const silentRefresh = useCallback(
    async (refreshToken: string): Promise<string | null> => {
      try {
        const session = await authRepository.refresh(refreshToken);
        await applySession(session);
        return session.accessToken;
      } catch {
        await clearSession();
        return null;
      }
    },
    [applySession, clearSession]
  );

  // Keep a ref so scheduleRefresh's setTimeout closure always calls the
  // latest silentRefresh without needing to re-create the timer callback.
  const silentRefreshRef = useRef(silentRefresh);
  silentRefreshRef.current = silentRefresh;

  useEffect(() => {
    registerRefreshHandler(async () => {
      const storedToken = await storage.secureGet(REFRESH_TOKEN_KEY, null);
      if (!storedToken) return null;
      return silentRefreshRef.current(storedToken);
    });
    return () => registerRefreshHandler(null);
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const storedToken = await storage.secureGet(REFRESH_TOKEN_KEY, null);
        if (storedToken) {
          await silentRefreshRef.current(storedToken);
        }
      } finally {
        setIsRestoring(false);
      }
    })();
    return () => {
      if (refreshTimer.current) clearTimeout(refreshTimer.current);
    };
  }, []);

  const signOut = useCallback(async () => {
    const storedToken = await storage.secureGet(REFRESH_TOKEN_KEY, null);
    if (storedToken) {
      try {
        await authRepository.logout(storedToken);
      } catch {
        // Best-effort server-side revoke — local state is cleared regardless
        // so the user is never stuck "logged in" on-device due to a network blip.
      }
    }
    await clearStoredDeliveryAddress();
    await clearSession();
  }, [clearSession]);

  const refreshProfile = useCallback(async () => {
    try {
      const profile = await authRepository.getProfile();
      setUser(profile.user);
    } catch {
      // If this fails because the session is gone, the next protected call
      // will already trigger the same 401 -> refresh -> (maybe) sign-out path.
    }
  }, []);

  const value = useMemo(
    () => ({
      user,
      isAuthenticated: !!user,
      isRestoring,
      applySession,
      signOut,
      refreshProfile,
    }),
    [user, isRestoring, applySession, signOut, refreshProfile]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider');
  return ctx;
}
