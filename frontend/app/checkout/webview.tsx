import React, { useRef, useState } from 'react';
import { View, StyleSheet, ActivityIndicator } from 'react-native';
import { WebView, WebViewNavigation } from 'react-native-webview';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { colors, radius, spacing } from '@/src/theme';
import { ThemedText, AnimatedPressable } from '@/src/shared/components';

/**
 * Shopify hosted checkout in an in-app WebView.
 * Monitors URL changes for Shopify's order-completion patterns and
 * navigates to the order confirmation screen when checkout succeeds.
 * No payment logic lives here — all payment is handled by Shopify.
 */

const SHOPIFY_SUCCESS_PATTERNS = [
  'thank_you',
  '/orders/',
  'order-status',
  'order_id=',
  'checkout/success',
];

function isCheckoutComplete(url: string): boolean {
  const lower = url.toLowerCase();
  return SHOPIFY_SUCCESS_PATTERNS.some((p) => lower.includes(p));
}

export default function CheckoutWebviewScreen() {
  const { checkoutUrl, cartId } = useLocalSearchParams<{ checkoutUrl: string; cartId: string }>();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const webviewRef = useRef<WebView>(null);

  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

  const handleNavigationChange = (navState: WebViewNavigation) => {
    const url = navState.url ?? '';
    if (isCheckoutComplete(url)) {
      // Extract order name from URL if possible (e.g. /orders/1234 or ?name=#1234)
      const orderMatch = url.match(/\/orders\/([^/?&]+)/i);
      const nameMatch = url.match(/[?&]name=([^&]+)/i);
      const orderRef = orderMatch?.[1] ?? nameMatch?.[1] ?? '';
      router.replace(
        `/checkout/confirmation?orderRef=${encodeURIComponent(orderRef)}&cartId=${encodeURIComponent(cartId ?? '')}`
      );
    }
  };

  if (!checkoutUrl) {
    return (
      <View style={[styles.screen, { paddingTop: insets.top }]}>
        <ThemedText variant="body" color={colors.status.error} testID="webview-missing-url">
          Checkout URL is missing. Please go back and try again.
        </ThemedText>
      </View>
    );
  }

  return (
    <View style={[styles.screen, { paddingTop: insets.top }]} testID="checkout-webview-screen">
      {/* Header */}
      <View style={styles.header}>
        <AnimatedPressable
          testID="webview-close-button"
          onPress={() => router.back()}
          scaleTo={0.9}
          hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
          style={styles.closeButton}
        >
          <Ionicons name="close" size={20} color={colors.text.primary} />
        </AnimatedPressable>
        <ThemedText variant="bodyBold" color={colors.text.primary}>Secure Checkout</ThemedText>
        <View style={styles.secureBadge}>
          <Ionicons name="lock-closed" size={11} color={colors.status.success} />
          <ThemedText variant="small" color={colors.status.success}>Secure</ThemedText>
        </View>
      </View>

      {/* Loading overlay */}
      {isLoading && (
        <View style={styles.loadingOverlay} testID="webview-loading">
          <ActivityIndicator color={colors.primary.main} size="large" />
          <ThemedText variant="body" color={colors.text.secondary} style={styles.loadingText}>
            Loading secure checkout…
          </ThemedText>
        </View>
      )}

      {/* Error state */}
      {loadError ? (
        <View style={styles.errorContainer} testID="webview-error">
          <Ionicons name="wifi-outline" size={40} color={colors.text.secondary} />
          <ThemedText variant="h3" color={colors.text.primary} style={{ marginTop: spacing.md }}>
            Could not load checkout
          </ThemedText>
          <ThemedText variant="body" color={colors.text.secondary}>
            Please check your connection and try again.
          </ThemedText>
          <AnimatedPressable
            testID="webview-retry-button"
            onPress={() => {
              setLoadError(false);
              webviewRef.current?.reload();
            }}
            scaleTo={0.96}
            style={styles.retryButton}
          >
            <ThemedText variant="bodyBold" color={colors.primary.main}>Retry</ThemedText>
          </AnimatedPressable>
        </View>
      ) : (
        <WebView
          ref={webviewRef}
          testID="shopify-checkout-webview"
          source={{ uri: checkoutUrl }}
          onLoadStart={() => setIsLoading(true)}
          onLoadEnd={() => setIsLoading(false)}
          onError={() => {
            setIsLoading(false);
            setLoadError(true);
          }}
          onNavigationStateChange={handleNavigationChange}
          // Allow Shopify's checkout JS + payment frames
          allowsInlineMediaPlayback
          mediaPlaybackRequiresUserAction={false}
          javaScriptEnabled
          domStorageEnabled
          startInLoadingState={false}
          style={styles.webview}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.background.base,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.border.default,
  },
  closeButton: {
    width: 36,
    height: 36,
    borderRadius: radius.pill,
    backgroundColor: colors.background.surface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  secureBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 3,
    backgroundColor: 'rgba(34, 197, 94, 0.12)',
    borderRadius: radius.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
  },
  webview: {
    flex: 1,
    backgroundColor: '#FFFFFF',
  },
  loadingOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: colors.background.base,
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.md,
    zIndex: 10,
  },
  loadingText: {
    marginTop: spacing.sm,
  },
  errorContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: spacing.xl,
    gap: spacing.sm,
  },
  retryButton: {
    marginTop: spacing.md,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.xl,
    backgroundColor: 'rgba(139, 92, 246, 0.15)',
    borderRadius: radius.pill,
  },
});
