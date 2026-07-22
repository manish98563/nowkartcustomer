/**
 * Domain model for a live Shopify Cart, managed via the Shopify Cart API
 * (through our backend) — no customer login required.
 */
export interface CartLine {
  id: string;
  quantity: number;
  variantId: string;
  productHandle: string;
  title: string;
  variantTitle?: string | null;
  imageUrl?: string | null;
  price: number;
  currencyCode: string;
  lineTotal: number;
  availableForSale: boolean;
  quantityAvailable?: number | null;
}

export interface Cart {
  id: string;
  checkoutUrl: string;
  totalQuantity: number;
  subtotal: number;
  total: number;
  totalTax: number;
  currencyCode: string;
  lines: CartLine[];
}

export interface CartLineIssue {
  lineId: string;
  title: string;
  message: string;
}

export interface CheckoutPreparation {
  cart: Cart;
  isValid: boolean;
  issues: CartLineIssue[];
  checkoutUrl: string;
}
