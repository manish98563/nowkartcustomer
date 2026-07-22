import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Product } from '@/src/types';

const WISHLIST_STORAGE_KEY = 'nowkart_wishlist_v1';

interface WishlistContextValue {
  items: Product[];
  ids: string[];
  count: number;
  isLoading: boolean;
  isWishlisted: (productId: string) => boolean;
  toggleWishlist: (product: Product) => void;
  removeFromWishlist: (productId: string) => void;
}

const WishlistContext = createContext<WishlistContextValue | undefined>(undefined);

/**
 * Wishlist is persisted locally (AsyncStorage) today, storing full Product
 * snapshots keyed by product ID so the Wishlist screen renders instantly
 * without any refetch. This is intentionally the ONLY place wishlist state
 * lives — the Header badge and every screen's heart icon all read from this
 * single context, so they can never drift out of sync with each other.
 *
 * Forward-compatible by design: once customer accounts support a synced
 * wishlist (e.g. Shopify metafields, or our own Mongo collection keyed by
 * shopifyCustomerId), only the load/persist functions below need to change
 * to also read/write the backend when `useAuth().isAuthenticated` is true —
 * no consuming screen would need to change at all.
 */
export function WishlistProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<Product[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const raw = await AsyncStorage.getItem(WISHLIST_STORAGE_KEY);
        if (raw) setItems(JSON.parse(raw));
      } catch {
        // Corrupt/missing local data — start with an empty wishlist rather
        // than crash the app.
      } finally {
        setIsLoading(false);
      }
    })();
  }, []);

  const persist = useCallback((next: Product[]) => {
    setItems(next);
    AsyncStorage.setItem(WISHLIST_STORAGE_KEY, JSON.stringify(next)).catch(() => {});
  }, []);

  const isWishlisted = useCallback((productId: string) => items.some((p) => p.id === productId), [items]);

  const toggleWishlist = useCallback(
    (product: Product) => {
      const exists = items.some((p) => p.id === product.id);
      persist(exists ? items.filter((p) => p.id !== product.id) : [...items, product]);
    },
    [items, persist]
  );

  const removeFromWishlist = useCallback(
    (productId: string) => {
      persist(items.filter((p) => p.id !== productId));
    },
    [items, persist]
  );

  const ids = useMemo(() => items.map((p) => p.id), [items]);

  const value = useMemo(
    () => ({ items, ids, count: items.length, isLoading, isWishlisted, toggleWishlist, removeFromWishlist }),
    [items, ids, isLoading, isWishlisted, toggleWishlist, removeFromWishlist]
  );

  return <WishlistContext.Provider value={value}>{children}</WishlistContext.Provider>;
}

export function useWishlist(): WishlistContextValue {
  const ctx = useContext(WishlistContext);
  if (!ctx) throw new Error('useWishlist must be used within a WishlistProvider');
  return ctx;
}
