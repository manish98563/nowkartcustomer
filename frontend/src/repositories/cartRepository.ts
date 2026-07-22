import { apiClient } from '@/src/services/api/apiClient';
import { Cart, CheckoutPreparation, Address } from '@/src/types';

/**
 * Data-access abstraction over the live Shopify Cart API, proxied through
 * our backend. Cart/line IDs are Shopify GIDs (contain `://` and `?`), so
 * they're always sent via query string / JSON body — never as raw URL
 * path segments — to avoid encoding pitfalls.
 */
export const cartRepository = {
  createCart: (variantId: string, quantity = 1): Promise<Cart> =>
    apiClient.post<Cart>('/shopify/cart', { variantId, quantity }),

  getCart: (cartId: string): Promise<Cart> =>
    apiClient.get<Cart>(`/shopify/cart?cart_id=${encodeURIComponent(cartId)}`),

  addLine: (cartId: string, variantId: string, quantity = 1): Promise<Cart> =>
    apiClient.post<Cart>('/shopify/cart/lines', { cartId, variantId, quantity }),

  updateLineQuantity: (cartId: string, lineId: string, quantity: number): Promise<Cart> =>
    apiClient.put<Cart>('/shopify/cart/lines', { cartId, lineId, quantity }),

  removeLine: (cartId: string, lineId: string): Promise<Cart> =>
    apiClient.delete<Cart>('/shopify/cart/lines', { cartId, lineId }),

  /**
   * Validates the cart against live Shopify stock and attaches the signed-in
   * customer's buyer identity. Pass the selected delivery address so Shopify
   * Checkout opens with the shipping address already pre-populated.
   */
  prepareCheckout: (cartId: string, selectedAddress?: Address | null): Promise<CheckoutPreparation> =>
    apiClient.post<CheckoutPreparation>('/shopify/checkout/prepare', {
      cartId,
      ...(selectedAddress
        ? {
            deliveryFirstName: selectedAddress.firstName ?? undefined,
            deliveryLastName: selectedAddress.lastName ?? undefined,
            deliveryAddress1: selectedAddress.address1 ?? undefined,
            deliveryAddress2: selectedAddress.address2 ?? undefined,
            deliveryCity: selectedAddress.city ?? undefined,
            deliveryTerritoryCode: selectedAddress.territoryCode ?? undefined,
            deliveryZip: selectedAddress.zip ?? undefined,
            deliveryPhone: selectedAddress.phoneNumber ?? undefined,
          }
        : {}),
    }),

  /** Attach a delivery instruction note to the cart as a Shopify cart attribute. */
  updateNote: (cartId: string, note: string): Promise<{ ok: boolean }> =>
    apiClient.put<{ ok: boolean }>('/shopify/cart/note', { cartId, note }),
};

// (duplicate declaration removed — see the cartRepository above)
