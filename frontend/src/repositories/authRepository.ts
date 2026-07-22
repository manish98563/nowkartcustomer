import { apiClient } from '@/src/services/api/apiClient';
import { Address, AddressInput, AuthSession, OrderDetail, Profile } from '@/src/types';

/**
 * Talks ONLY to our own backend's /api/auth/* routes.
 */
export const authRepository = {
  getAuthorizeUrl: (
    codeChallenge: string,
    platform: 'native' | 'web',
    origin?: string
  ): Promise<{ authorizeUrl: string; state: string; redirectUri: string }> =>
    apiClient.post('/auth/shopify/authorize-url', { codeChallenge, platform, origin }),

  exchangeCode: (code: string, state: string, codeVerifier: string, redirectUri: string): Promise<AuthSession> =>
    apiClient.post('/auth/shopify/token-exchange', { code, state, codeVerifier, redirectUri }),

  refresh: (refreshToken: string): Promise<AuthSession> => apiClient.post('/auth/refresh', { refreshToken }),

  logout: (refreshToken: string): Promise<{ ok: boolean }> => apiClient.post('/auth/logout', { refreshToken }),

  getProfile: (): Promise<Profile> => apiClient.get('/auth/me'),

  /** Full order detail including line items, price breakdown, fulfillments.
   * Uses a query param (?id=) instead of a path segment to safely pass
   * Shopify GIDs (which contain slashes) through the Kubernetes ingress. */
  getOrder: (orderId: string): Promise<OrderDetail> =>
    apiClient.get(`/auth/orders?id=${encodeURIComponent(orderId)}`),

  createAddress: (address: AddressInput, setDefault = false): Promise<Address> =>
    apiClient.post(`/auth/addresses${setDefault ? '?set_default=true' : ''}`, address),

  updateAddress: (addressId: string, address: AddressInput, setDefault = false): Promise<Address> =>
    apiClient.put(
      `/auth/addresses?addressId=${encodeURIComponent(addressId)}${setDefault ? '&set_default=true' : ''}`,
      address
    ),

  deleteAddress: (addressId: string): Promise<{ ok: boolean }> =>
    apiClient.delete(`/auth/addresses?addressId=${encodeURIComponent(addressId)}`),
};

// authRepository is defined once above. No duplicate.
