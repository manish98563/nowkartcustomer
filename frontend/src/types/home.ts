import { Product } from './product';

/**
 * A titled horizontal rail of products on the Home screen
 * (e.g. "Best Sellers", "New Arrivals"), backed by a live Shopify
 * collection when one exists, or a sitewide sorted query as a fallback.
 */
export interface ProductRail {
  title: string;
  handle?: string | null;
  products: Product[];
}

export interface HomeSections {
  categoryGroups: import('./category').CategoryGroup[];
  rails: ProductRail[];
}
