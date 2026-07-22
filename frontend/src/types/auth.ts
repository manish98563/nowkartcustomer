/**
 * Domain models for Now Kart's own backend-issued session + the Shopify
 * Customer Account profile data it fronts. The device NEVER sees a real
 * Shopify customer token — only these backend-issued shapes.
 */
export interface AuthUser {
  id: string;
  email?: string | null;
  firstName?: string | null;
  lastName?: string | null;
}

export interface AuthSession {
  accessToken: string;
  refreshToken: string;
  expiresIn: number;
  user: AuthUser;
}

export interface Address {
  id: string;
  firstName?: string | null;
  lastName?: string | null;
  address1?: string | null;
  address2?: string | null;
  city?: string | null;
  zoneCode?: string | null;
  territoryCode?: string | null;
  zip?: string | null;
  phoneNumber?: string | null;
  isDefault: boolean;
}

export interface AddressInput {
  firstName?: string;
  lastName?: string;
  address1: string;
  address2?: string;
  city: string;
  zoneCode?: string;
  territoryCode: string;
  zip?: string;
  phoneNumber?: string;
}

export interface OrderSummary {
  id: string;
  name: string;
  processedAt: string;
  cancelledAt?: string | null;
  financialStatus?: string | null;
  fulfillmentStatus?: string | null;
  totalPrice: number;
  currencyCode: string;
  itemCount: number;
  thumbnailUrl?: string | null;
}

export interface OrderLineItem {
  id: string;
  title: string;
  quantity: number;
  imageUrl?: string | null;
  price: number;
  originalPrice: number;
  currencyCode: string;
}

export interface OrderFulfillment {
  id: string;
  createdAt?: string | null;
  updatedAt?: string | null;
}

export interface OrderDetail {
  id: string;
  name: string;
  processedAt: string;
  cancelledAt?: string | null;
  cancelReason?: string | null;
  financialStatus?: string | null;
  fulfillmentStatus?: string | null;
  email?: string | null;
  totalPrice: number;
  subtotal?: number | null;
  totalTax?: number | null;
  totalShipping?: number | null;
  totalRefunded?: number | null;
  currencyCode: string;
  statusPageUrl?: string | null;
  shippingAddress?: Address | null;
  lineItems: OrderLineItem[];
  fulfillments: OrderFulfillment[];
}

export interface Profile {
  user: AuthUser;
  addresses: Address[];
  orders: OrderSummary[];
}
