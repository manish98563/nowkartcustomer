import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { cartRepository } from '@/src/repositories';
import { ApiError } from '@/src/services/api/apiClient';
import { Cart } from '@/src/types';

const CART_ID_STORAGE_KEY = 'nowkart_cart_id';

interface CartContextValue {
  cart: Cart | null;
  cartCount: number;
  isLoading: boolean;
  error: string | null;
  addItem: (variantId: string, quantity?: number) => Promise<void>;
  updateLineQuantity: (lineId: string, quantity: number) => Promise<void>;
  removeLine: (lineId: string) => Promise<void>;
  clearCart: () => Promise<void>;
}

const CartContext = createContext<CartContextValue | undefined>(undefined);

/**
 * Global cart state backed by the live Shopify Cart API (via our backend).
 * The cart ID is persisted locally so the same cart survives app restarts —
 * no customer login required (guest cart, per this iteration's scope).
 */
export function CartProvider({ children }: { children: React.ReactNode }) {
  const [cart, setCart] = useState<Cart | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const storedId = await AsyncStorage.getItem(CART_ID_STORAGE_KEY);
        if (storedId) {
          try {
            const restored = await cartRepository.getCart(storedId);
            setCart(restored);
          } catch {
            await AsyncStorage.removeItem(CART_ID_STORAGE_KEY);
          }
        }
      } finally {
        setIsLoading(false);
      }
    })();
  }, []);

  const persistCart = useCallback(async (nextCart: Cart) => {
    setCart(nextCart);
    await AsyncStorage.setItem(CART_ID_STORAGE_KEY, nextCart.id);
  }, []);

  const addItem = useCallback(
    async (variantId: string, quantity = 1) => {
      setError(null);
      try {
        if (!cart) {
          const created = await cartRepository.createCart(variantId, quantity);
          await persistCart(created);
        } else {
          const updated = await cartRepository.addLine(cart.id, variantId, quantity);
          await persistCart(updated);
        }
      } catch (e) {
        setError(e instanceof ApiError ? e.message : 'Could not add item to cart.');
      }
    },
    [cart, persistCart]
  );

  const updateLineQuantity = useCallback(
    async (lineId: string, quantity: number) => {
      if (!cart) return;
      setError(null);
      try {
        const updated = await cartRepository.updateLineQuantity(cart.id, lineId, quantity);
        await persistCart(updated);
      } catch (e) {
        setError(e instanceof ApiError ? e.message : 'Could not update cart.');
      }
    },
    [cart, persistCart]
  );

  const removeLine = useCallback(
    async (lineId: string) => {
      if (!cart) return;
      setError(null);
      try {
        const updated = await cartRepository.removeLine(cart.id, lineId);
        await persistCart(updated);
      } catch (e) {
        setError(e instanceof ApiError ? e.message : 'Could not remove item.');
      }
    },
    [cart, persistCart]
  );

  const clearCart = useCallback(async () => {
    setCart(null);
    await AsyncStorage.removeItem(CART_ID_STORAGE_KEY);
  }, []);

  const value = useMemo(
    () => ({
      cart,
      cartCount: cart?.totalQuantity ?? 0,
      isLoading,
      error,
      addItem,
      updateLineQuantity,
      removeLine,
      clearCart,
    }),
    [cart, isLoading, error, addItem, updateLineQuantity, removeLine, clearCart]
  );

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

export function useCart(): CartContextValue {
  const ctx = useContext(CartContext);
  if (!ctx) throw new Error('useCart must be used within a CartProvider');
  return ctx;
}
