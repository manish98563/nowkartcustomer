import { apiClient } from '@/src/services/api/apiClient';
import { Category, CategoryGroup, HomeSections, Product } from '@/src/types';

interface CollectionProductsResponse {
  collection: Category;
  products: Product[];
}

/**
 * Data-access abstraction over live Shopify product/collection data.
 * Talks ONLY to our backend (/api/shopify/*) — never to Shopify directly.
 */
export const productRepository = {
  getHomeSections: (): Promise<HomeSections> => apiClient.get<HomeSections>('/shopify/home'),

  getCategoryGroups: (): Promise<CategoryGroup[]> => apiClient.get<CategoryGroup[]>('/shopify/categories'),

  getCollectionProducts: (handle: string, first = 24): Promise<CollectionProductsResponse> =>
    apiClient.get<CollectionProductsResponse>(`/shopify/collections/${handle}/products?first=${first}`),

  getProductByHandle: (handle: string): Promise<Product> => apiClient.get<Product>(`/shopify/products/${handle}`),

  searchProducts: (query: string, first = 20): Promise<Product[]> =>
    apiClient.get<Product[]>(`/shopify/search?q=${encodeURIComponent(query)}&first=${first}`),
};
