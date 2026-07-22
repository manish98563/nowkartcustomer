/**
 * Order Tracking Screen — app/order/track.tsx
 *
 * Shows the live order status pulled from Shopify fulfillment data.
 * Auto-refreshes every 30 seconds while the order is ACTIVE and the
 * screen is focused + app is in foreground.
 *
 * Polling stops automatically for:
 *   • FULFILLED orders (delivered)
 *   • CANCELLED orders
 *   • App in background (AppState)
 *   • Screen out of focus (useFocusEffect cleanup)
 *
 * ARCHITECTURE PREP:
 * When the Rider App ships, riderLocation/riderEta will be added to
 * TrackingStatus. This screen renders them without needing a redesign:
 *   • riderLocation → MapView (new import, same screen)
 *   • riderEta → replace ETA pill text
 *   • riderName/Phone → add to delivery card
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  View,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  AppState,
  AppStateStatus,
  RefreshControl,
} from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useFocusEffect } from '@react-navigation/native';
import { Ionicons } from '@expo/vector-icons';
import { Image } from 'expo-image';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Animated, {
  FadeIn,
  FadeInDown,
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withTiming,
} from 'react-native-reanimated';
import { colors, radius, spacing, shadows } from '@/src/theme';
import { ThemedText, AnimatedPressable, ErrorState, Button } from '@/src/shared/components';
import { useAuth } from '@/src/features/auth/AuthContext';
import { trackingRepository } from '@/src/repositories';
import { ApiError } from '@/src/services/api/apiClient';
import { TrackingStatus, TrackingStage } from '@/src/types';

const POLL_INTERVAL_MS = 30_000; // 30 s — respectful of Shopify rate limits
const POLL_COUNTDOWN_MS = 1_000;  // countdown tick

/* ── Pulsing dot for active status ────────────────────────────────────── */
function PulsingDot({ color }: { color: string }) {
  const opacity = useSharedValue(1);
  useEffect(() => {
    opacity.value = withRepeat(withTiming(0.3, { duration: 900 }), -1, true);
  }, [opacity]);
  const style = useAnimatedStyle(() => ({ opacity: opacity.value }));
  return (
    <Animated.View style={[styles.pulsingDot, { backgroundColor: color }, style]} />
  );
}

/* ── Main screen ───────────────────────────────────────────────────────── */
export default function OrderTrackScreen() {
  const { orderId } = useLocalSearchParams<{ orderId: string }>();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { isAuthenticated, isRestoring } = useAuth();

  const [tracking, setTracking] = useState<TrackingStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [countdown, setCountdown] = useState(POLL_INTERVAL_MS / 1000);

  const appStateRef = useRef<AppStateStatus>('active');
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const countdownTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ── Fetch ──────────────────────────────────────────────────────────────
  const fetchTracking = useCallback(
    async (isRefresh = false) => {
      if (!orderId) {
        setIsLoading(false);
        setError('Order ID is missing.');
        return;
      }
      if (isRefresh) setIsRefreshing(true);
      else if (!tracking) setIsLoading(true);
      setError(null);
      try {
        const data = await trackingRepository.getTrackingStatus(orderId);
        setTracking(data);
        setCountdown(POLL_INTERVAL_MS / 1000);
      } catch (e) {
        if (!tracking) {
          setError(e instanceof ApiError ? e.message : 'Could not load tracking information.');
        }
        // If we already have data, silently fail (keep showing last known state)
      } finally {
        setIsLoading(false);
        setIsRefreshing(false);
      }
    },
    [orderId, tracking]
  );

  // ── Initial load ────────────────────────────────────────────────────────
  useEffect(() => {
    if (isAuthenticated) fetchTracking(false);
    else if (!isRestoring) {
      setIsLoading(false);
      setError('Please sign in to track your order.');
    }
  }, [isAuthenticated, isRestoring]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Auto-refresh polling (only for active orders) ───────────────────────
  const startPolling = useCallback(() => {
    if (!tracking?.isActive) return;
    // clear any existing timers before starting new ones
    if (pollTimerRef.current) clearInterval(pollTimerRef.current);
    if (countdownTimerRef.current) clearInterval(countdownTimerRef.current);

    countdownTimerRef.current = setInterval(() => {
      setCountdown((c) => (c > 1 ? c - 1 : POLL_INTERVAL_MS / 1000));
    }, POLL_COUNTDOWN_MS);

    pollTimerRef.current = setInterval(() => {
      if (appStateRef.current === 'active') {
        fetchTracking(false);
      }
    }, POLL_INTERVAL_MS);
  }, [tracking?.isActive, fetchTracking]);

  const stopPolling = useCallback(() => {
    if (pollTimerRef.current) clearInterval(pollTimerRef.current);
    if (countdownTimerRef.current) clearInterval(countdownTimerRef.current);
    pollTimerRef.current = null;
    countdownTimerRef.current = null;
  }, []);

  // Start/stop polling when tracking data changes
  useEffect(() => {
    if (tracking?.isActive) startPolling();
    else stopPolling();
    return stopPolling;
  }, [tracking?.isActive, startPolling, stopPolling]);

  // Pause polling when screen loses focus
  useFocusEffect(
    useCallback(() => {
      if (tracking?.isActive) startPolling();
      return stopPolling;
    }, [tracking?.isActive, startPolling, stopPolling])
  );

  // Background-safe: pause polling when app goes to background
  useEffect(() => {
    const sub = AppState.addEventListener('change', (nextState: AppStateStatus) => {
      appStateRef.current = nextState;
      if (nextState !== 'active') stopPolling();
      else if (tracking?.isActive) startPolling();
    });
    return () => sub.remove();
  }, [tracking?.isActive, startPolling, stopPolling]);

  // ── Helpers ─────────────────────────────────────────────────────────────
  const stageColor = (stage: TrackingStage) => {
    if (stage.key === 'cancelled') return colors.status.error;
    if (stage.done) return colors.status.success;
    if (stage.active) return colors.primary.main;
    return colors.border.default;
  };

  const currentStageColor = () => {
    if (!tracking) return colors.primary.main;
    if (tracking.currentStage === 'cancelled') return colors.status.error;
    if (tracking.currentStage === 'delivered') return colors.status.success;
    return colors.primary.main;
  };

  const sym = tracking?.currencyCode === 'GBP' ? '£' : '$';

  function formatLastUpdated(ts?: string | null): string {
    if (!ts) return 'Unknown';
    const d = new Date(ts);
    return d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
  }

  // ── Render ───────────────────────────────────────────────────────────────
  if (!orderId) {
    return (
      <View style={[styles.screen, { paddingTop: insets.top }]}>
        <ThemedText variant="body" color={colors.status.error}>No order ID provided.</ThemedText>
      </View>
    );
  }

  return (
    <View style={[styles.screen, { paddingTop: insets.top + spacing.sm }]} testID="order-track-screen">
      {/* ── Header ── */}
      <View style={styles.headerRow}>
        <AnimatedPressable
          testID="track-back-button"
          onPress={() => router.back()}
          scaleTo={0.94}
          hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
          style={styles.backButton}
        >
          <Ionicons name="chevron-back" size={18} color={colors.text.primary} />
          <ThemedText variant="bodyBold" color={colors.text.primary}>
            {tracking ? tracking.orderName : 'Track Order'}
          </ThemedText>
        </AnimatedPressable>
        {tracking?.isActive && (
          <View style={styles.liveBadge} testID="track-live-badge">
            <PulsingDot color={colors.status.success} />
            <ThemedText variant="small" color={colors.status.success}>LIVE</ThemedText>
          </View>
        )}
      </View>

      {isLoading ? (
        <View style={styles.centered}>
          <ActivityIndicator color={colors.primary.main} size="large" testID="track-loading" />
          <ThemedText variant="small" color={colors.text.secondary} style={{ marginTop: spacing.md }}>
            Loading tracking info…
          </ThemedText>
        </View>
      ) : error ? (
        <ErrorState
          testID="track-error-state"
          subtitle={error}
          onRetry={isAuthenticated ? () => fetchTracking(false) : undefined}
        />
      ) : tracking ? (
        <ScrollView
          showsVerticalScrollIndicator={false}
          contentContainerStyle={[styles.scrollContent, { paddingBottom: insets.bottom + spacing.xl }]}
          refreshControl={
            <RefreshControl
              refreshing={isRefreshing}
              onRefresh={() => fetchTracking(true)}
              tintColor={colors.primary.main}
              testID="track-refresh-control"
            />
          }
          testID="track-scroll"
        >
          {/* ── Current Status Hero ── */}
          <Animated.View entering={FadeIn.duration(350)} style={[styles.heroCard, { borderColor: currentStageColor() + '40' }]} testID="track-status-hero">
            <View style={styles.heroTop}>
              <View style={[styles.heroIconWrap, { backgroundColor: currentStageColor() + '20' }]}>
                {tracking.isActive ? (
                  <PulsingDot color={currentStageColor()} />
                ) : (
                  <Ionicons
                    name={tracking.currentStage === 'cancelled' ? 'close-circle' : 'checkmark-circle'}
                    size={28}
                    color={currentStageColor()}
                  />
                )}
              </View>
              <View style={styles.heroText}>
                <ThemedText variant="h2" color={colors.text.primary} testID="track-current-stage">
                  {tracking.currentStageLabel}
                </ThemedText>
                <ThemedText variant="small" color={colors.text.secondary}>
                  Order {tracking.orderName}
                </ThemedText>
              </View>
            </View>

            {/* ETA / status message */}
            <View style={styles.etaRow} testID="track-eta-row">
              <Ionicons name="time-outline" size={14} color={colors.text.secondary} />
              <ThemedText variant="small" color={colors.text.secondary}>
                {tracking.estimatedDelivery
                  ? `Est. delivery: ${new Date(tracking.estimatedDelivery).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })}`
                  : tracking.currentStage === 'delivered'
                  ? 'Your order has been delivered'
                  : tracking.currentStage === 'cancelled'
                  ? 'Your order was cancelled'
                  : tracking.currentStage === 'out_for_delivery'
                  ? 'Your order is on its way'
                  : tracking.currentStage === 'preparing'
                  ? 'Your order is being prepared'
                  : tracking.currentStage === 'confirmed'
                  ? 'Payment confirmed, preparing soon'
                  : 'Order received'}
              </ThemedText>
            </View>

            {/* Last updated + auto-refresh countdown */}
            <View style={styles.updatedRow}>
              <ThemedText variant="small" color={colors.text.secondary} testID="track-last-updated">
                Updated {formatLastUpdated(tracking.lastUpdatedAt)}
              </ThemedText>
              {tracking.isActive && (
                <ThemedText variant="small" color={colors.text.secondary} testID="track-countdown">
                  · Refreshing in {countdown}s
                </ThemedText>
              )}
            </View>
          </Animated.View>

          {/* ── Timeline ── */}
          <Animated.View entering={FadeInDown.duration(300).delay(80)} style={styles.card} testID="track-timeline">
            <View style={styles.cardHeader}>
              <Ionicons name="git-merge-outline" size={18} color={colors.primary.main} />
              <ThemedText variant="h3" color={colors.text.primary}>Delivery Progress</ThemedText>
            </View>
            {tracking.stages.map((stage, i) => (
              <View key={stage.key} style={styles.timelineRow} testID={`track-stage-${stage.key}`}>
                <View style={styles.timelineLeft}>
                  <View style={[styles.timelineDot, { backgroundColor: stageColor(stage), borderColor: stageColor(stage) }]}>
                    {stage.active && tracking.isActive ? (
                      <PulsingDot color="#FFFFFF" />
                    ) : (
                      <Ionicons
                        name={stage.icon as any}
                        size={11}
                        color={stage.done || stage.active ? '#FFFFFF' : colors.text.secondary}
                      />
                    )}
                  </View>
                  {i < tracking.stages.length - 1 && (
                    <View style={[styles.timelineLine, stage.done && styles.timelineLineDone]} />
                  )}
                </View>
                <View style={styles.timelineRight}>
                  <ThemedText
                    variant={stage.active ? 'bodyBold' : 'body'}
                    color={stage.done || stage.active ? colors.text.primary : colors.text.secondary}
                  >
                    {stage.label}
                  </ThemedText>
                  {stage.timestamp && (
                    <ThemedText variant="small" color={colors.text.secondary}>
                      {new Date(stage.timestamp).toLocaleString('en-GB', {
                        day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
                      })}
                    </ThemedText>
                  )}
                </View>
              </View>
            ))}
          </Animated.View>

          {/* ── Delivery address ── */}
          {tracking.deliveryAddress && (
            <Animated.View entering={FadeInDown.duration(300).delay(140)} style={styles.card} testID="track-delivery-address">
              <View style={styles.cardHeader}>
                <Ionicons name="location-outline" size={18} color={colors.primary.main} />
                <ThemedText variant="h3" color={colors.text.primary}>Delivering to</ThemedText>
              </View>
              <ThemedText variant="bodyBold" color={colors.text.primary}>
                {[tracking.deliveryAddress.firstName, tracking.deliveryAddress.lastName]
                  .filter(Boolean).join(' ') || 'Delivery Address'}
              </ThemedText>
              <ThemedText variant="body" color={colors.text.secondary}>
                {[
                  tracking.deliveryAddress.address1,
                  tracking.deliveryAddress.city,
                  tracking.deliveryAddress.zip,
                ].filter(Boolean).join(', ')}
              </ThemedText>
            </Animated.View>
          )}

          {/* ── Order items (compact) ── */}
          {tracking.items.length > 0 && (
            <Animated.View entering={FadeInDown.duration(300).delay(180)} style={styles.card} testID="track-items">
              <View style={styles.cardHeader}>
                <Ionicons name="bag-handle-outline" size={18} color={colors.primary.main} />
                <ThemedText variant="h3" color={colors.text.primary}>
                  {tracking.items.length} {tracking.items.length === 1 ? 'Item' : 'Items'}
                </ThemedText>
                <ThemedText variant="bodyBold" color={colors.primary.main} style={{ marginLeft: 'auto' }}>
                  {sym}{tracking.totalPrice.toFixed(2)}
                </ThemedText>
              </View>
              {tracking.items.map((item) => (
                <View key={item.id} style={styles.itemRow} testID={`track-item-${item.id}`}>
                  <View style={styles.itemImageWrap}>
                    {item.imageUrl ? (
                      <Image source={{ uri: item.imageUrl }} style={styles.itemImage} contentFit="contain" />
                    ) : (
                      <Ionicons name="image-outline" size={16} color={colors.text.inverseSecondary} />
                    )}
                  </View>
                  <View style={styles.itemInfo}>
                    <ThemedText variant="body" color={colors.text.inverse} numberOfLines={1}>
                      {item.title}
                    </ThemedText>
                    <ThemedText variant="small" color={colors.text.inverseSecondary}>
                      Qty: {item.quantity}
                    </ThemedText>
                  </View>
                  <ThemedText variant="small" color={colors.text.inverse}>
                    {sym}{item.price.toFixed(2)}
                  </ThemedText>
                </View>
              ))}
            </Animated.View>
          )}

          {/* ── Actions ── */}
          <Animated.View entering={FadeInDown.duration(300).delay(220)} style={styles.actions}>
            <Button
              testID="track-view-details-button"
              label="View Full Order Details"
              variant="outline"
              fullWidth
              onPress={() =>
                router.push(`/order/detail?orderId=${encodeURIComponent(tracking.orderId)}`)
              }
            />
            <Button
              testID="track-continue-shopping-button"
              label="Continue Shopping"
              fullWidth
              onPress={() => {
                router.dismissAll();
                router.replace('/(tabs)');
              }}
              style={{ marginTop: spacing.xs }}
            />
          </Animated.View>
        </ScrollView>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background.base },
  centered: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
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
  liveBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    backgroundColor: 'rgba(34,197,94,0.12)',
    borderRadius: radius.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
  },
  pulsingDot: { width: 8, height: 8, borderRadius: 4 },
  scrollContent: { paddingHorizontal: spacing.lg, gap: spacing.md },
  // Hero status card
  heroCard: {
    backgroundColor: colors.background.surface,
    borderRadius: radius.xl,
    padding: spacing.lg,
    gap: spacing.md,
    borderWidth: 1.5,
    ...shadows.soft,
  },
  heroTop: { flexDirection: 'row', alignItems: 'center', gap: spacing.md },
  heroIconWrap: {
    width: 56, height: 56, borderRadius: 28,
    alignItems: 'center', justifyContent: 'center',
  },
  heroText: { flex: 1, gap: 2 },
  etaRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
  updatedRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    flexWrap: 'wrap',
  },
  // Shared card
  card: {
    backgroundColor: colors.background.surface,
    borderRadius: radius.lg,
    padding: spacing.lg,
    gap: spacing.sm,
    ...shadows.soft,
  },
  cardHeader: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, marginBottom: spacing.xs },
  // Timeline
  timelineRow: { flexDirection: 'row', alignItems: 'flex-start', gap: spacing.md, minHeight: 44 },
  timelineLeft: { width: 26, alignItems: 'center' },
  timelineDot: {
    width: 26, height: 26, borderRadius: 13,
    alignItems: 'center', justifyContent: 'center',
    borderWidth: 2, borderColor: colors.border.default,
  },
  timelineLine: {
    width: 2, flex: 1, backgroundColor: colors.border.default,
    marginTop: 2, minHeight: 18,
  },
  timelineLineDone: { backgroundColor: colors.status.success },
  timelineRight: { flex: 1, paddingTop: 3, gap: 2 },
  // Items
  itemRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    backgroundColor: colors.cards.productBg,
    borderRadius: radius.md,
    padding: spacing.sm,
  },
  itemImageWrap: {
    width: 40, height: 40, borderRadius: radius.sm,
    backgroundColor: '#F5F5F5', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
  },
  itemImage: { width: '80%', height: '80%' },
  itemInfo: { flex: 1, gap: 2 },
  // Actions
  actions: { gap: spacing.sm, marginTop: spacing.sm },
});
