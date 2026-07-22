/**
 * Domain model for a Category — maps 1:1 to a live Shopify `Collection`.
 */
export interface Category {
  id: string;
  handle: string;
  title: string;
  description?: string | null;
  groupTitle: string;
  imageUrl?: string | null;
}

export interface CategoryGroup {
  groupTitle: string;
  categories: Category[];
}
