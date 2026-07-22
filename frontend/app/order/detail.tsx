import React, { useCallback, useEffect, useState } from 'react';
import {
  View,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  RefreshControl,
} from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Image } from 'expo-image';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Animated, { FadeIn, FadeInDown } from 'react-native-reanimated';
import { colors, radius, spacing, shadows } from '@/src/theme';
import { ThemedText, Button, AnimatedPressable, ErrorState } from '@/src/shared/components';
import { useAuth } from '@/src/features/auth/AuthContext';
import { useCart } from '@/src/features/cart/CartContext';
import { authRepository, productRepository } from '@/src/repositories';
import { ApiError } from '@/src/services/api/apiClient';
import { OrderDetail, OrderLineItem } from '@/src/types';

/* ── Timeline helpers ─────────────────────────────────────────────────── */

type TimelineStage = {
  key: string;
  label: string;
  done: boolean;
  active: boolean;
  icon: string;
};

function buildTimeline(order: OrderDetail): TimelineStage[] {
  const cancelled = !!order.cancelledAt;
  const fs = (order.fulfillmentStatus ?? '').toUpperCase();
  const paid = ['PAID', 'PARTIALLY_PAID', 'AUTHORIZED'].includes(
    (order.financialStatus ?? '').toUpperCase()
  );
  const fulfilled = fs === 'FULFILLED';
  const partial = fs === 'PARTIALLY_FULFILLED' || fs === 'PARTIAL';
  const hasFulfillment = order.fulfillments.length > 0;

  if (cancelled) {
    return [
      { key: 'placed', label: 'Order Placed', done: true, active: false, icon: 'receipt-outline' },
      { key: 'cancelled', label: `Cancelled${order.cancelReason ? ' — ' + order.cancelReason : ''}`, done: true, active: true, icon: 'close-circle-outline' },
    ];
  }

  return [
    { key: 'placed', label: 'Order Placed', done: true, active: false, icon: 'receipt-outline' },
    { key: 'confirmed', label: 'Payment Confirmed', done: paid, active: !paid, icon: 'card-outline' },
    { key: 'preparing', label: 'Preparing Order', done: hasFulfillment || partial || fulfilled, active: !hasFulfillment && !partial && !fulfilled && paid, icon: 'cube-outline' },
    { key: 'delivery', label: 'Out for Delivery', done: fulfilled, active: hasFulfillment && !fulfilled, icon: 'bicycle-outline' },
    { key: 'delivered', label: 'Delivered', done: fulfilled, active: false, icon: 'checkmark-circle-outline' },
  ];
}

/* ── Main screen ──────────────────────────────────────────────────────── */

export default function OrderDetailScreen() {
  const { orderId } = useLocalSearchParams<{ orderId: string }>();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { isAuthenticated, isRestoring } = useAuth();
  const { addItem } = useCart();

  const [order, setOrder] = useState<OrderDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reorderingId, setReorderingId] = useState<string | null>(null);
  const [reorderFeedback, setReorderFeedback] = useState<string | null>(null);

  const load = useCallback(
    async (isRefresh = false) => {
      if (!orderId) {
        setIsLoading(false);
        setError('Order ID is missing.');
        return;
      }
      if (isRefresh) setIsRefreshing(true);
      else setIsLoading(true);
      setError(null);
      try {
        const detail = await authRepository.getOrder(orderId);
        setOrder(detail);
      } catch (e) {
        setError(e instanceof ApiError ? e.message : 'Could not load this order.');
      } finally {
        setIsLoading(false);
        setIsRefreshing(false);
      }
    },
    [orderId]
  );

  useEffect(() => {
    if (isAuthenticated) load();
    else if (!isRestoring) {
      setIsLoading(false);
      setError('Please sign in to view order details.');
    }
  }, [isAuthenticated, isRestoring, load]);

  const handleReorderItem = async (line: OrderLineItem) => {
    setReorderingId(line.id);
    setReorderFeedback(null);
    try {
      // Search Shopify for this product by title to get a Storefront variant ID
      const results = await productRepository.searchProducts(line.title.substring(0, 30));
      const match = results[0];
      if (!match || !match.variants[0]) {
        setReorderFeedback(`"${line.title}" is no longer available.`);
        return;
      }
      if (!match.inStock) {
        setReorderFeedback(`"${line.title}" is currently out of stock.`);
        return;
      }
      await addItem(match.variants[0].id, 1);
      setReorderFeedback(`Added "${line.title}" to cart.`);
    } catch {
      setReorderFeedback(`Could not add "${line.title}" to cart. Please try again.`);
    } finally {
      setReorderingId(null);
      setTimeout(() => setReorderFeedback(null), 3000);
    }
  };

  const handleReorderAll = async () => {
    if (!order) return;
    setReorderingId('all');
    setReorderFeedback(null);
    let added = 0;
    let failed = 0;
    for (const line of order.lineItems) {
      try {
        const results = await productRepository.searchProducts(line.title.substring(0, 30));
        const match = results[0];
        if (match?.inStock && match.variants[0]) {
          await addItem(match.variants[0].id, 1);
          added++;
        } else {
          failed++;
        }
      } catch {
        failed++;
      }
    }
    setReorderingId(null);
    if (added > 0 && failed === 0) {
      setReorderFeedback(`Added ${added} item${added !== 1 ? 's' : ''} to cart.`);
    } else if (added > 0) {
      setReorderFeedback(`Added ${added} item${added !== 1 ? 's' : ''} (${failed} unavailable).`);
    } else {
      setReorderFeedback('None of these items are currently available.');
    }
    setTimeout(() => setReorderFeedback(null), 4000);
  };

  if (!orderId) {
    return (
      <View style={[styles.screen, { paddingTop: insets.top }]}>
        <ThemedText variant="body" color={colors.status.error}>No order ID provided.</ThemedText>
      </View>
    );
  }

  const sym = order?.currencyCode === 'GBP' ? '£' : '$';
  const timeline = order ? buildTimeline(order) : [];
  const isOrderActive = order
    ? !order.cancelledAt && (order.fulfillmentStatus ?? '').toUpperCase() !== 'FULFILLED'
    : false;

  return (
    <View style={[styles.screen, { paddingTop: insets.top + spacing.sm }]} testID="order-detail-screen">
      {/* ── Header ── */}
      <View style={styles.headerRow}>
        <AnimatedPressable
          testID="order-detail-back-button"
          onPress={() => router.back()}
          scaleTo={0.94}
          hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
          style={styles.backButton}
        >
          <Ionicons name="chevron-back" size={18} color={colors.text.primary} />
          <ThemedText variant="bodyBold" color={colors.text.primary}>Orders</ThemedText>
        </AnimatedPressable>
        {order && (
          <ThemedText variant="bodyBold" color={colors.text.secondary}>{order.name}</ThemedText>
        )}
      </View>

      {isLoading ? (
        <View style={styles.centered}>
          <ActivityIndicator color={colors.primary.main} size="large" testID="order-detail-loading" />
        </View>
      ) : error ? (
        <ErrorState testID="order-detail-error" subtitle={error} onRetry={isAuthenticated ? () => load() : undefined} />
      ) : order ? (
        <ScrollView
          showsVerticalScrollIndicator={false}
          contentContainerStyle={[styles.scrollContent, { paddingBottom: insets.bottom + spacing.xl }]}
          refreshControl={
            <RefreshControl
              refreshing={isRefreshing}
              onRefresh={() => load(true)}
              tintColor={colors.primary.main}
            />
          }
          testID="order-detail-scroll"
        >
          {/* ── Reorder feedback banner ── */}
          {reorderFeedback && (
            <Animated.View entering={FadeIn.duration(250)} style={styles.feedbackBanner} testID="reorder-feedback">
              <Ionicons name="information-circle-outline" size={16} color={colors.text.secondary} />
              <ThemedText variant="small" color={colors.text.secondary} style={{ flex: 1 }}>
                {reorderFeedback}
              </ThemedText>
            </Animated.View>
          )}

          {/* ── Order summary card ── */}
          <Animated.View entering={FadeInDown.duration(300).delay(0)} style={styles.card} testID="order-summary-card">
            <View style={styles.summaryRow}>
              <ThemedText variant="h2" color={colors.text.primary} testID="order-name">{order.name}</ThemedText>
              <ThemedText variant="h3" color={colors.primary.main} testID="order-total">
                {sym}{order.totalPrice.toFixed(2)}
              </ThemedText>
            </View>
            <ThemedText variant="small" color={colors.text.secondary} testID="order-date">
              {new Date(order.processedAt).toLocaleDateString('en-GB', {
                weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
              })}
            </ThemedText>
            <View style={styles.badgeRow}>
              {order.financialStatus && (
                <View style={styles.badge}>
                  <ThemedText variant="small" color={colors.text.secondary} testID="order-payment-status">
                    {order.financialStatus}
                  </ThemedText>
                </View>
              )}
              {order.fulfillmentStatus && (
                <View style={[styles.badge, { backgroundColor: 'rgba(139,92,246,0.12)' }]}>
                  <ThemedText variant="small" color={colors.primary.main} testID="order-fulfillment-status">
                    {order.cancelledAt ? 'Cancelled' : order.fulfillmentStatus}
                  </ThemedText>
                </View>
              )}
            </View>
            <Button
              testID="order-reorder-all-button"
              label={reorderingId === 'all' ? 'Adding to Cart…' : 'Reorder All'}
              variant="outline"
              fullWidth
              loading={reorderingId === 'all'}
              onPress={handleReorderAll}
              style={{ marginTop: spacing.sm }}
            />
          </Animated.View>

          {/* ── Order Timeline ── */}
          <Animated.View entering={FadeInDown.duration(300).delay(80)} style={styles.card} testID="order-timeline">
            <View style={styles.cardHeader}>
              <Ionicons name="time-outline" size={18} color={colors.primary.main} />
              <ThemedText variant="h3" color={colors.text.primary}>Order Status</ThemedText>
            </View>
            {timeline.map((stage, i) => (
              <View key={stage.key} style={styles.timelineRow} testID={`timeline-stage-${stage.key}`}>
                <View style={styles.timelineLeft}>
                  <View style={[
                    styles.timelineDot,
                    stage.done && styles.timelineDotDone,
                    stage.active && styles.timelineDotActive,
                  ]}>
                    <Ionicons
                      name={stage.icon as any}
                      size={12}
                      color={stage.done || stage.active ? '#FFFFFF' : colors.text.secondary}
                    />
                  </View>
                  {i < timeline.length - 1 && (
                    <View style={[styles.timelineLine, stage.done && styles.timelineLineDone]} />
                  )}
                </View>
                <ThemedText
                  variant={stage.active ? 'bodyBold' : 'body'}
                  color={stage.done || stage.active ? colors.text.primary : colors.text.secondary}
                  style={styles.timelineLabel}
                >
                  {stage.label}
                </ThemedText>
              </View>
            ))}
          </Animated.View>

          {/* ── Line items ── */}
          <Animated.View entering={FadeInDown.duration(300).delay(120)} style={styles.card} testID="order-line-items">
            <View style={styles.cardHeader}>
              <Ionicons name="bag-handle-outline" size={18} color={colors.primary.main} />
              <ThemedText variant="h3" color={colors.text.primary}>
                Items ({order.lineItems.length})
              </ThemedText>
            </View>
            {order.lineItems.map((line) => (
              <View key={line.id} style={styles.lineRow} testID={`order-line-${line.id}`}>
                <View style={styles.lineImageWrap}>
                  {line.imageUrl ? (
                    <Image source={{ uri: line.imageUrl }} style={styles.lineImage} contentFit="contain" />
                  ) : (
                    <Ionicons name="image-outline" size={20} color={colors.text.inverseSecondary} />
                  )}
                </View>
                <View style={styles.lineInfo}>
                  <ThemedText variant="bodyBold" color={colors.text.inverse} numberOfLines={2}>
                    {line.title}
                  </ThemedText>
                  <ThemedText variant="small" color={colors.text.inverseSecondary}>
                    Qty: {line.quantity} · {sym}{line.price.toFixed(2)}
                  </ThemedText>
                </View>
                <AnimatedPressable
                  testID={`reorder-item-${line.id}`}
                  onPress={() => handleReorderItem(line)}
                  scaleTo={0.9}
                  style={[styles.addBtn, reorderingId === line.id && styles.addBtnLoading]}
                  disabled={!!reorderingId}
                >
                  <Ionicons
                    name={reorderingId === line.id ? 'hourglass-outline' : 'add'}
                    size={16}
                    color={colors.primary.main}
                  />
                </AnimatedPressable>
              </View>
            ))}
          </Animated.View>

          {/* ── Price breakdown ── */}
          <Animated.View entering={FadeInDown.duration(300).delay(160)} style={styles.card} testID="order-price-breakdown">
            <View style={styles.cardHeader}>
              <Ionicons name="receipt-outline" size={18} color={colors.primary.main} />
              <ThemedText variant="h3" color={colors.text.primary}>Price Breakdown</ThemedText>
            </View>
            {order.subtotal != null && (
              <PriceRow label="Subtotal" value={`${sym}${order.subtotal.toFixed(2)}`} testID="order-subtotal" />
            )}
            {order.totalShipping != null && (
              <PriceRow
                label="Delivery"
                value={order.totalShipping === 0 ? 'Free' : `${sym}${order.totalShipping.toFixed(2)}`}
                highlight={order.totalShipping === 0}
                testID="order-shipping"
              />
            )}
            {(order.totalTax ?? 0) > 0 && (
              <PriceRow label="Tax" value={`${sym}${order.totalTax!.toFixed(2)}`} testID="order-tax" />
            )}
            {(order.totalRefunded ?? 0) > 0 && (
              <PriceRow label="Refunded" value={`-${sym}${order.totalRefunded!.toFixed(2)}`} testID="order-refunded" />
            )}
            <View style={styles.totalRow}>
              <ThemedText variant="h3" color={colors.text.primary}>Total</ThemedText>
              <ThemedText variant="h2" color={colors.primary.main} testID="order-grand-total">
                {sym}{order.totalPrice.toFixed(2)}
              </ThemedText>
            </View>
          </Animated.View>

          {/* ── Delivery address ── */}
          {order.shippingAddress && (
            <Animated.View entering={FadeInDown.duration(300).delay(200)} style={styles.card} testID="order-shipping-address">
              <View style={styles.cardHeader}>
                <Ionicons name="location-outline" size={18} color={colors.primary.main} />
                <ThemedText variant="h3" color={colors.text.primary}>Delivery Address</ThemedText>
              </View>
              <ThemedText variant="bodyBold" color={colors.text.primary}>
                {[order.shippingAddress.firstName, order.shippingAddress.lastName]
                  .filter(Boolean)
                  .join(' ') || 'Delivery Address'}
              </ThemedText>
              <ThemedText variant="body" color={colors.text.secondary}>
                {[
                  order.shippingAddress.address1,
                  order.shippingAddress.address2,
                  order.shippingAddress.city,
                  order.shippingAddress.zip,
                  order.shippingAddress.territoryCode,
                ]
                  .filter(Boolean)
                  .join(', ')}
              </ThemedText>
              {order.shippingAddress.phoneNumber && (
                <ThemedText variant="small" color={colors.text.secondary}>
                  {order.shippingAddress.phoneNumber}
                </ThemedText>
              )}
            </Animated.View>
          )}

          {/* ── Actions ── */}
          <Animated.View entering={FadeInDown.duration(300).delay(240)} style={styles.actions}>
            {isOrderActive && (
              <Button
                testID="order-detail-track-button"
                label="Track Order"
                fullWidth
                onPress={() =>
                  router.push(`/order/track?orderId=${encodeURIComponent(order.id)}`)
                }
              />
            )}
            <Button
              testID="order-detail-continue-shopping"
              label="Continue Shopping"
              variant={isOrderActive ? 'outline' : 'primary'}
              fullWidth
              onPress={() => {
                router.dismissAll();
                router.replace('/(tabs)');
              }}
            />
          </Animated.View>
        </ScrollView>
      ) : null}
    </View>
  );
}

/* ── Sub-components ─────────────────────────────────────────────────── */

function PriceRow({
  label,
  value,
  highlight,
  testID,
}: {
  label: string;
  value: string;
  highlight?: boolean;
  testID?: string;
}) {
  return (
    <View style={styles.priceRow}>
      <ThemedText variant="body" color={colors.text.secondary}>{label}</ThemedText>
      <ThemedText
        variant="bodyBold"
        color={highlight ? colors.status.success : colors.text.primary}
        testID={testID}
      >
        {value}
      </ThemedText>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.background.base,
  },
  centered: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.md,
  },
  backButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.background.surface,
    borderRadius: radius.pill,
    paddingVertical: spacing.xs + 2,
    paddingHorizontal: spacing.md,
    gap: 2,
  },
  scrollContent: {
    paddingHorizontal: spacing.lg,
    gap: spacing.md,
  },
  feedbackBanner: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.sm,
    backgroundColor: colors.background.surface,
    borderRadius: radius.md,
    padding: spacing.md,
  },
  card: {
    backgroundColor: colors.background.surface,
    borderRadius: radius.lg,
    padding: spacing.lg,
    gap: spacing.sm,
    ...shadows.soft,
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginBottom: spacing.xs,
  },
  summaryRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  badgeRow: {
    flexDirection: 'row',
    gap: spacing.sm,
    marginTop: spacing.xs,
  },
  badge: {
    backgroundColor: colors.background.base,
    borderRadius: radius.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
  },
  // Timeline
  timelineRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.md,
    minHeight: 40,
  },
  timelineLeft: {
    width: 24,
    alignItems: 'center',
  },
  timelineDot: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: colors.background.base,
    borderWidth: 2,
    borderColor: colors.border.default,
    alignItems: 'center',
    justifyContent: 'center',
  },
  timelineDotDone: {
    backgroundColor: colors.status.success,
    borderColor: colors.status.success,
  },
  timelineDotActive: {
    backgroundColor: colors.primary.main,
    borderColor: colors.primary.main,
  },
  timelineLine: {
    width: 2,
    flex: 1,
    backgroundColor: colors.border.default,
    marginTop: 2,
    minHeight: 16,
  },
  timelineLineDone: {
    backgroundColor: colors.status.success,
  },
  timelineLabel: {
    flex: 1,
    paddingTop: 3,
  },
  // Line items
  lineRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    backgroundColor: colors.cards.productBg,
    borderRadius: radius.md,
    padding: spacing.sm,
  },
  lineImageWrap: {
    width: 48,
    height: 48,
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
  addBtn: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: 'rgba(139,92,246,0.12)',
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
  },
  addBtnLoading: {
    opacity: 0.5,
  },
  // Price breakdown
  priceRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  totalRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingTop: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.border.default,
    marginTop: spacing.xs,
  },
  actions: {
    gap: spacing.sm,
    marginTop: spacing.sm,
  },
});
