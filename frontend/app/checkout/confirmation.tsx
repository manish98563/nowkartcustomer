import React, { useEffect, useState } from 'react';
import { View, ScrollView, StyleSheet } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Image } from 'expo-image';
import Animated, { FadeIn, ZoomIn } from 'react-native-reanimated';
import { colors, radius, spacing, shadows } from '@/src/theme';
import { ThemedText, Button, AnimatedPressable } from '@/src/shared/components';
import { useAuth } from '@/src/features/auth/AuthContext';
import { useCart } from '@/src/features/cart/CartContext';
import { authRepository } from '@/src/repositories';
import { CartLine, OrderSummary } from '@/src/types';

/**
 * Order confirmation screen — shown after Shopify checkout completion.
 * For authenticated users: fetches the latest order from /api/auth/me.
 * For guests: shows confirmation using the cart snapshot before it's cleared.
 * Always clears the local cart after displaying.
 */
export default function CheckoutConfirmationScreen() {
  const { orderRef } = useLocalSearchParams<{ orderRef: string }>();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { isAuthenticated } = useAuth();
  const { cart, clearCart } = useCart();

  const [latestOrder, setLatestOrder] = useState<OrderSummary | null>(null);
  const [cartSnapshot] = useState(cart); // snapshot before clearCart

  useEffect(() => {
    // Fetch latest order for authenticated users
    if (isAuthenticated) {
      authRepository.getProfile().then((profile) => {
        if (profile.orders.length > 0) {
          setLatestOrder(profile.orders[0]);
        }
      }).catch(() => {/* non-blocking */});
    }
    // Clear cart after snapshot captured
    clearCart();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const orderName = latestOrder?.name ?? (orderRef ? decodeURIComponent(orderRef) : null);
  const symbol = cartSnapshot?.currencyCode === 'GBP' ? '£' : '$';
  const totalPaid = latestOrder
    ? `${latestOrder.currencyCode === 'GBP' ? '£' : '$'}${latestOrder.totalPrice.toFixed(2)}`
    : cartSnapshot
    ? `${symbol}${cartSnapshot.total.toFixed(2)}`
    : null;

  return (
    <View style={[styles.screen, { paddingTop: insets.top }]} testID="checkout-confirmation-screen">
      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={[styles.scrollContent, { paddingBottom: insets.bottom + spacing.xl }]}
      >
        {/* Success icon */}
        <Animated.View entering={ZoomIn.duration(500)} style={styles.successIconWrap}>
          <View style={styles.successCircle}>
            <Ionicons name="checkmark" size={48} color="#FFFFFF" />
          </View>
        </Animated.View>

        <Animated.View entering={FadeIn.delay(300).duration(400)} style={styles.headerText}>
          <ThemedText variant="h1" color={colors.text.primary} style={styles.centered} testID="confirmation-title">
            Order Placed!
          </ThemedText>
          <ThemedText variant="body" color={colors.text.secondary} style={styles.centered}>
            Thank you for your order. You'll receive a confirmation email shortly.
          </ThemedText>
        </Animated.View>

        {/* Order details card */}
        <Animated.View entering={FadeIn.delay(450).duration(400)} style={styles.detailsCard} testID="confirmation-details">
          {/* Order reference */}
          {orderName ? (
            <View style={styles.detailRow}>
              <ThemedText variant="small" color={colors.text.secondary}>Order</ThemedText>
              <ThemedText variant="bodyBold" color={colors.text.primary} testID="confirmation-order-name">
                {orderName}
              </ThemedText>
            </View>
          ) : null}

          {/* Estimated delivery */}
          <View style={styles.detailRow}>
            <ThemedText variant="small" color={colors.text.secondary}>Estimated delivery</ThemedText>
            <View style={styles.etaBadge} testID="confirmation-eta">
              <Ionicons name="bicycle-outline" size={13} color={colors.primary.main} />
              <ThemedText variant="bodyBold" color={colors.primary.main}>30–45 minutes</ThemedText>
            </View>
          </View>

          {/* Order total */}
          {totalPaid && (
            <View style={styles.detailRow}>
              <ThemedText variant="small" color={colors.text.secondary}>Total paid</ThemedText>
              <ThemedText variant="bodyBold" color={colors.text.primary} testID="confirmation-total">
                {totalPaid}
              </ThemedText>
            </View>
          )}

          {/* Financial status */}
          {latestOrder?.financialStatus && (
            <View style={styles.detailRow}>
              <ThemedText variant="small" color={colors.text.secondary}>Payment</ThemedText>
              <View style={styles.statusBadge}>
                <ThemedText variant="small" color={colors.status.success}>
                  {latestOrder.financialStatus}
                </ThemedText>
              </View>
            </View>
          )}
        </Animated.View>

        {/* Ordered items */}
        {(cartSnapshot?.lines ?? []).length > 0 && (
          <Animated.View entering={FadeIn.delay(550).duration(400)} style={styles.itemsCard} testID="confirmation-items">
            <ThemedText variant="h3" color={colors.text.primary} style={styles.itemsTitle}>
              Your Order
            </ThemedText>
            {(cartSnapshot?.lines ?? []).map((line) => (
              <ConfirmationLineRow key={line.id} line={line} symbol={symbol} />
            ))}
          </Animated.View>
        )}

        {/* Actions */}
        <Animated.View entering={FadeIn.delay(650).duration(400)} style={styles.actions}>
          <Button
            testID="confirmation-view-orders-button"
            label="View Orders"
            variant="outline"
            fullWidth
            onPress={() => {
              router.dismissAll();
              router.push('/(tabs)/orders');
            }}
          />
          <Button
            testID="confirmation-continue-shopping-button"
            label="Continue Shopping"
            fullWidth
            onPress={() => {
              router.dismissAll();
              router.replace('/(tabs)');
            }}
            style={styles.continueButton}
          />
        </Animated.View>
      </ScrollView>
    </View>
  );
}

function ConfirmationLineRow({ line, symbol }: { line: CartLine; symbol: string }) {
  return (
    <View style={styles.lineRow} testID={`confirmation-line-${line.id}`}>
      <View style={styles.lineImageWrap}>
        {line.imageUrl ? (
          <Image source={{ uri: line.imageUrl }} style={styles.lineImage} contentFit="contain" />
        ) : (
          <Ionicons name="image-outline" size={18} color={colors.text.inverseSecondary} />
        )}
      </View>
      <View style={styles.lineInfo}>
        <ThemedText variant="bodyBold" color={colors.text.inverse} numberOfLines={2}>
          {line.title}
        </ThemedText>
        <ThemedText variant="small" color={colors.text.inverseSecondary}>
          Qty: {line.quantity}
          {line.variantTitle ? ` · ${line.variantTitle}` : ''}
        </ThemedText>
      </View>
      <ThemedText variant="bodyBold" color={colors.text.inverse}>
        {symbol}{line.lineTotal.toFixed(2)}
      </ThemedText>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.background.base,
  },
  scrollContent: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.xl,
    gap: spacing.lg,
  },
  centered: {
    textAlign: 'center',
  },
  successIconWrap: {
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  successCircle: {
    width: 96,
    height: 96,
    borderRadius: 48,
    backgroundColor: colors.status.success,
    alignItems: 'center',
    justifyContent: 'center',
    ...shadows.elevation,
  },
  headerText: {
    gap: spacing.sm,
    alignItems: 'center',
  },
  detailsCard: {
    backgroundColor: colors.background.surface,
    borderRadius: radius.lg,
    padding: spacing.lg,
    gap: spacing.md,
    ...shadows.soft,
  },
  detailRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  etaBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    backgroundColor: 'rgba(139, 92, 246, 0.15)',
    borderRadius: radius.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
  },
  statusBadge: {
    backgroundColor: 'rgba(34, 197, 94, 0.12)',
    borderRadius: radius.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
  },
  itemsCard: {
    backgroundColor: colors.background.surface,
    borderRadius: radius.lg,
    padding: spacing.lg,
    gap: spacing.sm,
    ...shadows.soft,
  },
  itemsTitle: {
    marginBottom: spacing.xs,
  },
  lineRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    backgroundColor: colors.cards.productBg,
    borderRadius: radius.md,
    padding: spacing.sm,
  },
  lineImageWrap: {
    width: 44,
    height: 44,
    borderRadius: radius.sm,
    backgroundColor: '#F5F5F5',
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
  },
  lineImage: {
    width: '80%',
    height: '80%',
  },
  lineInfo: {
    flex: 1,
    gap: 2,
  },
  actions: {
    gap: spacing.sm,
    marginTop: spacing.sm,
  },
  continueButton: {
    marginTop: spacing.xs,
  },
});
