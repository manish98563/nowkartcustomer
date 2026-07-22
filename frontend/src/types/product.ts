/**
 * Domain model for a Product, sourced live from the Shopify Storefront API
 * via our backend (/api/shopify/*). `id` is the Shopify GID.
 */
export interface SelectedOption {
  name: string;
  value: string;
}

export interface ProductVariant {
  id: string;
  title: string;
  price: number;
  compareAtPrice?: number | null;
  currencyCode: string;
  availableForSale: boolean;
  quantityAvailable?: number | null;
  selectedOptions: SelectedOption[];
  imageUrl?: string | null;
}

export interface Product {
  id: string;
  handle: string;
  title: string;
  description: string;
  price: number;
  compareAtPrice?: number | null;
  currencyCode: string;
  imageUrl?: string | null;
  images: string[];
  categoryHandle?: string | null;
  categoryTitle?: string | null;
  vendor?: string | null;
  inStock: boolean;
  variants: ProductVariant[];
}
