import React, { useCallback, useEffect, useState } from 'react';
import {
  View,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  RefreshControl,
  TextInput,
} from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Image } from 'expo-image';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Animated, { FadeInDown } from 'react-native-reanimated';
import { colors, radius, spacing, shadows } from '@/src/theme';
import { ThemedText, EmptyState, ErrorState, Button, AnimatedPressable } from '@/src/shared/components';
import { useAuth } from '@/src/features/auth/AuthContext';
import { authRepository } from '@/src/repositories';
import { ApiError } from '@/src/services/api/apiClient';
import { OrderSummary } from '@/src/types';

type FilterTab = 'all' | 'active' | 'completed' | 'cancelled';

function statusColor(fulfillmentStatus?: string | null, cancelledAt?: string | null): string {
  if (cancelledAt) return colors.status.error;
  const s = (fulfillmentStatus ?? '').toUpperCase();
  if (s === 'FULFILLED') return colors.status.success;
  if (s === 'PARTIAL' || s === 'PARTIALLY_FULFILLED') return '#F59E0B';
  return colors.primary.main;
}

function statusLabel(order: OrderSummary): string {
  if (order.cancelledAt) return 'Cancelled';
  const s = (order.fulfillmentStatus ?? '').toUpperCase();
  if (s === 'FULFILLED') return 'Delivered';
  if (s === 'PARTIAL' || s === 'PARTIALLY_FULFILLED') return 'Partially Fulfilled';
  if (s === 'UNFULFILLED') return 'Processing';
  return order.fulfillmentStatus ?? 'Processing';
}

function filterOrders(orders: OrderSummary[], tab: FilterTab, search: string): OrderSummary[] {
  let filtered = orders;
  if (tab === 'active') {
    filtered = orders.filter(
      (o) =>
        !o.cancelledAt &&
        o.fulfillmentStatus?.toUpperCase() !== 'FULFILLED'
    );
  } else if (tab === 'completed') {
    filtered = orders.filter((o) => o.fulfillmentStatus?.toUpperCase() === 'FULFILLED');
  } else if (tab === 'cancelled') {
    filtered = orders.filter((o) => !!o.cancelledAt);
  }
  if (search.trim()) {
    const q = search.trim().toLowerCase();
    filtered = filtered.filter((o) => o.name.toLowerCase().includes(q));
  }
  return filtered;
}

export default function OrdersScreen() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { isAuthenticated, isRestoring } = useAuth();

  const [orders, setOrders] = useState<OrderSummary[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<FilterTab>('all');
  const [search, setSearch] = useState('');

  const loadOrders = useCallback(async (isRefresh = false) => {
    if (isRefresh) setIsRefreshing(true);
    else setIsLoading(true);
    setError(null);
    try {
      const profile = await authRepository.getProfile();
      setOrders(profile.orders);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not load your orders.');
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    if (isAuthenticated) loadOrders();
  }, [isAuthenticated, loadOrders]);

  const displayedOrders = filterOrders(orders, activeTab, search);
  const symbol = (orders[0]?.currencyCode === 'GBP') ? '£' : '$';

  const TABS: { key: FilterTab; label: string }[] = [
    { key: 'all', label: 'All' },
    { key: 'active', label: 'Active' },
    { key: 'completed', label: 'Completed' },
    { key: 'cancelled', label: 'Cancelled' },
  ];

  return (
    <View style={[styles.screen, { paddingTop: insets.top + spacing.lg }]} testID="orders-screen">
      <ThemedText variant="h1" color={colors.text.primary} style={styles.title}>
        My Orders
      </ThemedText>

      {isRestoring ? (
        <ActivityIndicator color={colors.primary.main} />
      ) : !isAuthenticated ? (
        /* ── Guest gate ── */
        <View style={styles.centered} testID="orders-guest-view">
          <EmptyState
            testID="orders-signin-empty-state"
            iconName="cube-outline"
            title="Sign in to view your orders"
            subtitle="Your Now Kart order history appears here once you sign in."
          />
          <Button
            testID="orders-signin-button"
            label="Go to Profile"
            variant="outline"
            fullWidth
            onPress={() => router.push('/profile')}
            style={styles.signInButton}
          />
        </View>
      ) : isLoading ? (
        <ActivityIndicator color={colors.primary.main} testID="orders-loading" />
      ) : error ? (
        <ErrorState testID="orders-error-state" onRetry={() => loadOrders()} />
      ) : (
        <>
          {/* ── Search ── */}
          <View style={styles.searchRow} testID="orders-search-row">
            <Ionicons name="search-outline" size={16} color={colors.text.secondary} />
            <TextInput
              testID="orders-search-input"
              style={styles.searchInput}
              value={search}
              onChangeText={setSearch}
              placeholder="Search by order number…"
              placeholderTextColor={colors.text.secondary}
            />
            {search.length > 0 && (
              <AnimatedPressable testID="orders-search-clear" onPress={() => setSearch('')} scaleTo={0.85}>
                <Ionicons name="close-circle" size={16} color={colors.text.secondary} />
              </AnimatedPressable>
            )}
          </View>

          {/* ── Filter tabs ── */}
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            style={styles.tabsScroll}
            contentContainerStyle={styles.tabsContent}
            testID="orders-filter-tabs"
          >
            {TABS.map((tab) => (
              <AnimatedPressable
                key={tab.key}
                testID={`orders-tab-${tab.key}`}
                onPress={() => setActiveTab(tab.key)}
                scaleTo={0.94}
                style={[styles.tab, activeTab === tab.key && styles.tabActive]}
              >
                <ThemedText
                  variant="small"
                  color={activeTab === tab.key ? '#FFFFFF' : colors.text.secondary}
                >
                  {tab.label}
                </ThemedText>
              </AnimatedPressable>
            ))}
          </ScrollView>

          {/* ── Orders list ── */}
          <ScrollView
            showsVerticalScrollIndicator={false}
            contentContainerStyle={[
              styles.listContent,
              { paddingBottom: insets.bottom + spacing.xl },
            ]}
            refreshControl={
              <RefreshControl
                refreshing={isRefreshing}
                onRefresh={() => loadOrders(true)}
                tintColor={colors.primary.main}
                testID="orders-refresh-control"
              />
            }
            testID="orders-list"
          >
            {displayedOrders.length === 0 ? (
              <EmptyState
                testID="orders-empty-state"
                iconName="cube-outline"
                title={search ? 'No matching orders' : 'No orders here'}
                subtitle={search ? `No orders matching "${search}"` : 'Orders in this category will appear here.'}
              />
            ) : (
              displayedOrders.map((order, index) => (
                <Animated.View
                  key={order.id}
                  entering={FadeInDown.duration(250).delay(index * 40)}
                  testID={`order-card-${order.id}`}
                >
                  <AnimatedPressable
                    onPress={() =>
                      router.push(`/order/detail?orderId=${encodeURIComponent(order.id)}`)
                    }
                    scaleTo={0.97}
                    style={styles.orderCard}
                    testID={`order-card-press-${order.id}`}
                  >
                    {/* Row 1: order name + total */}
                    <View style={styles.cardRow}>
                      <ThemedText variant="bodyBold" color={colors.text.primary}>
                        {order.name}
                      </ThemedText>
                      <ThemedText variant="bodyBold" color={colors.primary.main}>
                        {symbol}{order.totalPrice.toFixed(2)}
                      </ThemedText>
                    </View>

                    {/* Row 2: date + item count */}
                    <ThemedText variant="small" color={colors.text.secondary}>
                      {new Date(order.processedAt).toLocaleDateString('en-GB', {
                        day: 'numeric',
                        month: 'short',
                        year: 'numeric',
                      })}
                      {order.itemCount > 0 ? ` · ${order.itemCount} item${order.itemCount !== 1 ? 's' : ''}` : ''}
                    </ThemedText>

                    {/* Row 3: status badge + thumbnail */}
                    <View style={styles.cardBottom}>
                      <View style={[styles.statusBadge, { backgroundColor: statusColor(order.fulfillmentStatus, order.cancelledAt) + '20' }]}>
                        <View style={[styles.statusDot, { backgroundColor: statusColor(order.fulfillmentStatus, order.cancelledAt) }]} />
                        <ThemedText
                          variant="small"
                          color={statusColor(order.fulfillmentStatus, order.cancelledAt)}
                          testID={`order-status-${order.id}`}
                        >
                          {statusLabel(order)}
                        </ThemedText>
                      </View>

                      {order.thumbnailUrl ? (
                        <View style={styles.thumbnail}>
                          <Image
                            source={{ uri: order.thumbnailUrl }}
                            style={styles.thumbnailImage}
                            contentFit="contain"
                            testID={`order-thumbnail-${order.id}`}
                          />
                        </View>
                      ) : null}
                    </View>

                    {/* Track button for active orders */}
                    {!order.cancelledAt && order.fulfillmentStatus?.toUpperCase() !== 'FULFILLED' && (
                      <AnimatedPressable
                        testID={`order-track-button-${order.id}`}
                        onPress={(e) => {
                          e.stopPropagation?.();
                          router.push(`/order/track?orderId=${encodeURIComponent(order.id)}`);
                        }}
                        scaleTo={0.96}
                        style={styles.trackButton}
                      >
                        <Ionicons name="navigate-outline" size={13} color={colors.primary.main} />
                        <ThemedText variant="small" color={colors.primary.main}>Track Order</ThemedText>
                      </AnimatedPressable>
                    )}

                    {/* Chevron */}
                    <Ionicons
                      name="chevron-forward"
                      size={14}
                      color={colors.text.secondary}
                      style={styles.chevron}
                    />
                  </AnimatedPressable>
                </Animated.View>
              ))
            )}
          </ScrollView>
        </>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.background.base,
    paddingHorizontal: spacing.lg,
  },
  title: {
    marginBottom: spacing.md,
  },
  centered: {
    flex: 1,
  },
  signInButton: {
    marginTop: spacing.lg,
  },
  searchRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    backgroundColor: colors.background.surface,
    borderRadius: radius.pill,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    marginBottom: spacing.md,
  },
  searchInput: {
    flex: 1,
    color: colors.text.primary,
    fontSize: 14,
    height: 24,
  },
  tabsScroll: {
    maxHeight: 44,
    marginBottom: spacing.md,
  },
  tabsContent: {
    gap: spacing.sm,
    alignItems: 'center',
  },
  tab: {
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.xs + 2,
    borderRadius: radius.pill,
    backgroundColor: colors.background.surface,
    flexShrink: 0,
  },
  tabActive: {
    backgroundColor: colors.primary.main,
  },
  listContent: {
    gap: spacing.md,
  },
  orderCard: {
    backgroundColor: colors.background.surface,
    borderRadius: radius.lg,
    padding: spacing.md,
    gap: spacing.xs,
    ...shadows.soft,
  },
  cardRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  cardBottom: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: spacing.xs,
  },
  statusBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    borderRadius: radius.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
  },
  statusDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  thumbnail: {
    width: 40,
    height: 40,
    borderRadius: radius.sm,
    backgroundColor: '#FFFFFF',
    overflow: 'hidden',
  },
  thumbnailImage: {
    width: '100%',
    height: '100%',
  },
  chevron: {
    position: 'absolute',
    right: spacing.md,
    top: '50%',
  },
  trackButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    alignSelf: 'flex-start',
    backgroundColor: 'rgba(139,92,246,0.10)',
    borderRadius: radius.pill,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    marginTop: spacing.xs,
  },
});
