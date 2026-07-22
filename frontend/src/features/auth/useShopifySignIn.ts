import { useCallback, useState } from 'react';
import { Platform } from 'react-native';
import * as WebBrowser from 'expo-web-browser';
import * as Linking from 'expo-linking';
import { authRepository } from '@/src/repositories';
import { ApiError } from '@/src/services/api/apiClient';
import { generatePkcePair } from '@/src/services/auth/pkce';
import { useAuth } from './AuthContext';

export type SignInStatus = 'success' | 'cancelled' | 'web-unsupported' | 'error';

export interface SignInResult {
  status: SignInStatus;
  message?: string;
}

/**
 * Drives the Shopify Customer Account OAuth2 + PKCE flow. The code_verifier
 * is generated here, on-device, and held only in a local variable for the
 * lifetime of this single call (standard native-app PKCE, per RFC 8252 and
 * Shopify's own requirements) — it is never persisted. Only the resulting
 * `{code, state, codeVerifier}` triple is sent, once, to our backend, which
 * performs the actual Shopify token exchange and keeps custody of the real
 * Shopify tokens. This hook never sees a Shopify access/refresh token.
 */
export function useShopifySignIn() {
  const { applySession } = useAuth();
  const [isSigningIn, setIsSigningIn] = useState(false);

  const signIn = useCallback(async (): Promise<SignInResult> => {
    if (Platform.OS === 'web') {
      // Only a native/mobile Customer Account API client is registered for
      // Now Kart today, so the interactive Shopify login can't complete in
      // a web preview — the OS-level custom-scheme redirect it relies on
      // only resolves inside a real iOS/Android app. Fail fast with a clear
      // message rather than attempting a request that can't succeed.
      return {
        status: 'web-unsupported',
        message: 'Sign-in is available in the Now Kart mobile app. Open this app on your phone to sign in.',
      };
    }

    setIsSigningIn(true);
    try {
      const { codeVerifier, codeChallenge } = await generatePkcePair();
      const { authorizeUrl, state, redirectUri } = await authRepository.getAuthorizeUrl(codeChallenge, 'native');

      const result = await WebBrowser.openAuthSessionAsync(authorizeUrl, redirectUri);
      if (result.type !== 'success' || !result.url) {
        return { status: 'cancelled' };
      }

      const parsed = Linking.parse(result.url);
      const code = parsed.queryParams?.code as string | undefined;
      const returnedState = parsed.queryParams?.state as string | undefined;
      const oauthError = parsed.queryParams?.error as string | undefined;

      if (oauthError) {
        return { status: 'error', message: 'Sign-in was not completed. Please try again.' };
      }
      if (!code || !returnedState || returnedState !== state) {
        return { status: 'error', message: 'Sign-in could not be verified. Please try again.' };
      }

      const session = await authRepository.exchangeCode(code, returnedState, codeVerifier, redirectUri);
      await applySession(session);
      return { status: 'success' };
    } catch (e) {
      return {
        status: 'error',
        message: e instanceof ApiError ? e.message : 'Could not sign in. Please try again.',
      };
    } finally {
      setIsSigningIn(false);
    }
  }, [applySession]);

  return { signIn, isSigningIn };
}
