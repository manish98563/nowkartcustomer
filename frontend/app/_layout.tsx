import 'react-native-reanimated';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { colors } from '@/src/theme';
import { CartProvider } from '@/src/features/cart/CartContext';
import { AuthProvider } from '@/src/features/auth/AuthContext';
import { WishlistProvider } from '@/src/features/wishlist/WishlistContext';

export default function RootLayout() {
  return (
    <SafeAreaProvider>
      <AuthProvider>
        <WishlistProvider>
          <CartProvider>
            <StatusBar style="light" />
            <Stack
              screenOptions={{
                headerShown: false,
                contentStyle: { backgroundColor: colors.background.base },
              }}
            >
              <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
              <Stack.Screen
                name="cart"
                options={{ presentation: 'card', animation: 'slide_from_bottom' }}
              />
              <Stack.Screen
                name="search"
                options={{ presentation: 'card', animation: 'slide_from_bottom' }}
              />
              <Stack.Screen
                name="product/[handle]"
                options={{ presentation: 'card', animation: 'slide_from_right' }}
              />
              <Stack.Screen
                name="collection/[handle]"
                options={{ presentation: 'card', animation: 'slide_from_right' }}
              />
              <Stack.Screen
                name="profile"
                options={{ presentation: 'card', animation: 'slide_from_right' }}
              />
              <Stack.Screen
                name="wishlist"
                options={{ presentation: 'card', animation: 'slide_from_right' }}
              />
              <Stack.Screen
                name="addresses"
                options={{ presentation: 'card', animation: 'slide_from_right' }}
              />
              <Stack.Screen
                name="checkout/address"
                options={{ presentation: 'card', animation: 'slide_from_right' }}
              />
              <Stack.Screen
                name="checkout/webview"
                options={{ presentation: 'fullScreenModal', animation: 'slide_from_bottom', gestureEnabled: false }}
              />
              <Stack.Screen
                name="checkout/confirmation"
                options={{ presentation: 'card', animation: 'fade', gestureEnabled: false }}
              />
              <Stack.Screen
                name="auth/callback"
                options={{ presentation: 'card', animation: 'fade' }}
              />
              <Stack.Screen
                name="order/detail"
                options={{ presentation: 'card', animation: 'slide_from_right' }}
              />
              <Stack.Screen
                name="order/track"
                options={{ presentation: 'card', animation: 'slide_from_right' }}
              />
            </Stack>
          </CartProvider>
        </WishlistProvider>
      </AuthProvider>
    </SafeAreaProvider>
  );
}
