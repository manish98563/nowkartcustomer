/**
 * Lightweight AsyncStorage helper for persisting the user's selected
 * delivery address across app restarts. Shopify is the system of record
 * for the address data; this is only a local display cache (address ID +
 * formatted fields so the Home screen can show it without an API call).
 *
 * Cleared on sign-out so stale address data is never shown for a
 * different account.
 */
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Address } from '@/src/types';

const KEY = 'nowkart_delivery_address_v1';

export async function getStoredDeliveryAddress(): Promise<Address | null> {
  try {
    const raw = await AsyncStorage.getItem(KEY);
    if (!raw) return null;
    return JSON.parse(raw) as Address;
  } catch {
    return null;
  }
}

export async function storeDeliveryAddress(address: Address): Promise<void> {
  try {
    await AsyncStorage.setItem(KEY, JSON.stringify(address));
  } catch {
    // Non-blocking
  }
}

export async function clearStoredDeliveryAddress(): Promise<void> {
  try {
    await AsyncStorage.removeItem(KEY);
  } catch {
    // Non-blocking
  }
}
