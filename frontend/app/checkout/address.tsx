import React, { useCallback, useEffect, useState } from 'react';
import {
  View,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  TextInput,
} from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Image } from 'expo-image';
import { colors, radius, spacing, shadows } from '@/src/theme';
import { ThemedText, Button, AnimatedPressable, ErrorState } from '@/src/shared/components';
import { useAuth } from '@/src/features/auth/AuthContext';
import { useCart } from '@/src/features/cart/CartContext';
import { cartRepository, authRepository } from '@/src/repositories';
import { ApiError } from '@/src/services/api/apiClient';
import { Address, CheckoutPreparation, CartLine } from '@/src/types';

const DELIVERY_FEE = 0; // Free delivery

export default function CheckoutAddressScreen() {
  const { cartId } = useLocalSearchParams<{ cartId: string }>();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { isAuthenticated } = useAuth();
  const { cart } = useCart();

  const [preparation, setPreparation] = useState<CheckoutPreparation | null>(null);
  const [addresses, setAddresses] = useState<Address[]>([]);
  const [selectedAddressId, setSelectedAddressId] = useState<string | null>(null);
  const [deliveryNote, setDeliveryNote] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isProceeding, setIsProceeding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!cartId) {
      setIsLoading(false);
      setError('No cart to check out. Please add items to your cart first.');
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const result = await cartRepository.prepareCheckout(cartId);
      setPreparation(result);
      if (isAuthenticated) {
        const profile = await authRepository.getProfile();
        setAddresses(profile.addresses);
        const defaultAddr = profile.addresses.find((a) => a.isDefault) ?? profile.addresses[0];
        if (defaultAddr) setSelectedAddressId(defaultAddr.id);
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not prepare checkout.');
    } finally {
      setIsLoading(false);
    }
  }, [cartId, isAuthenticated]);

  useEffect(() => {
    load();
  }, [load]);

  const handleProceed = async () => {
    if (!cartId) return;
    setIsProceeding(true);
    try {
      // Attach the selected delivery address so Shopify Checkout
      // pre-populates the shipping address field — no re-entry needed.
      const selectedAddress = addresses.find((a) => a.id === selectedAddressId) ?? null;
      const fresh = await cartRepository.prepareCheckout(cartId, selectedAddress);
      if (!fresh.isValid) {
        setPreparation(fresh);
        setIsProceeding(false);
        return;
      }
      if (deliveryNote.trim()) {
        await cartRepository.updateNote(cartId, deliveryNote.trim());
      }
      router.push(
        `/checkout/webview?checkoutUrl=${encodeURIComponent(fresh.checkoutUrl)}&cartId=${encodeURIComponent(cartId)}`
      );
    } catch {
      // Use the original checkoutUrl as fallback
      if (preparation?.checkoutUrl) {
        router.push(
          `/checkout/webview?checkoutUrl=${encodeURIComponent(preparation.checkoutUrl)}&cartId=${encodeURIComponent(cartId)}`
        );
      }
    } finally {
      setIsProceeding(false);
    }
  };

  const displayCart = preparation?.cart ?? cart;
  const currencyCode = displayCart?.currencyCode ?? 'GBP';
  const symbol = currencyCode === 'GBP' ? '£' : '$';

  return (
    <KeyboardAvoidingView
      style={{ flex: 1 }}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
    >
      <View style={[styles.screen, { paddingTop: insets.top + spacing.sm }]} testID="checkout-address-screen">
        {/* Header */}
        <View style={styles.headerRow}>
          <AnimatedPressable
            testID="checkout-back-button"
            onPress={() => router.back()}
            scaleTo={0.94}
            hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
            style={styles.backButton}
          >
            <Ionicons name="chevron-back" size={18} color={colors.text.primary} />
            <ThemedText variant="bodyBold" color={colors.text.primary}>Back</ThemedText>
          </AnimatedPressable>
          <ThemedText variant="h2" color={colors.text.primary}>Checkout</ThemedText>
        </View>

        {isLoading ? (
          <View style={styles.centered}>
            <ActivityIndicator color={colors.primary.main} testID="checkout-loading" size="large" />
          </View>
        ) : error ? (
          <ErrorState
            testID="checkout-error-state"
            subtitle={error}
            onRetry={cartId ? load : () => router.back()}
          />
        ) : preparation && !preparation.isValid ? (
          /* ── Cart Issues ── */
          <View style={styles.issuesContainer} testID="checkout-issues">
            <View style={styles.issueHeader}>
              <Ionicons name="alert-circle" size={24} color={colors.status.error} />
              <ThemedText variant="h3" color={colors.text.primary}>Please review your cart</ThemedText>
            </View>
            {preparation.issues.length === 0 ? (
              <ThemedText variant="body" color={colors.text.secondary}>Your cart is empty.</ThemedText>
            ) : (
              preparation.issues.map((issue) => (
                <View key={issue.lineId} style={styles.issueRow} testID={`checkout-issue-${issue.lineId}`}>
                  <Ionicons name="remove-circle-outline" size={16} color={colors.status.error} />
                  <ThemedText variant="body" color={colors.text.secondary} style={styles.issueText}>
                    {issue.message}
                  </ThemedText>
                </View>
              ))
            )}
            <Button
              testID="checkout-review-cart-button"
              label="Review Cart"
              fullWidth
              onPress={() => router.back()}
              style={styles.actionButton}
            />
          </View>
        ) : (
          /* ── Main Checkout Flow ── */
          <ScrollView
            showsVerticalScrollIndicator={false}
            contentContainerStyle={[styles.scrollContent, { paddingBottom: insets.bottom + 100 }]}
            keyboardShouldPersistTaps="handled"
            testID="checkout-content"
          >
            {/* ── 1. Order Summary ── */}
            <SectionCard title="Order Summary" icon="bag-handle-outline">
              {(displayCart?.lines ?? []).map((line) => (
                <OrderLineRow key={line.id} line={line} symbol={symbol} />
              ))}

              <View style={styles.divider} />

              <PriceRow label="Subtotal" value={`${symbol}${(displayCart?.subtotal ?? 0).toFixed(2)}`} testID="checkout-subtotal" />
              {(displayCart?.totalTax ?? 0) > 0 && (
                <PriceRow
                  label="Tax"
                  value={`${symbol}${(displayCart?.totalTax ?? 0).toFixed(2)}`}
                  testID="checkout-tax"
                />
              )}
              <PriceRow
                label="Delivery"
                value={DELIVERY_FEE === 0 ? 'Free' : `${symbol}${DELIVERY_FEE.toFixed(2)}`}
                testID="checkout-delivery-fee"
                highlight={DELIVERY_FEE === 0}
              />
              <View style={styles.totalRow}>
                <ThemedText variant="h3" color={colors.text.primary}>Total</ThemedText>
                <ThemedText variant="h2" color={colors.primary.main} testID="checkout-total">
                  {symbol}{((displayCart?.total ?? 0) + DELIVERY_FEE).toFixed(2)}
                </ThemedText>
              </View>
            </SectionCard>

            {/* ── 2. Delivery Address ── */}
            <SectionCard title="Delivery Address" icon="location-outline">
              {isAuthenticated ? (
                addresses.length > 0 ? (
                  <>
                    {addresses.map((address) => (
                      <AnimatedPressable
                        key={address.id}
                        testID={`checkout-address-${address.id}`}
                        onPress={() => setSelectedAddressId(address.id)}
                        scaleTo={0.98}
                        style={[
                          styles.addressOption,
                          selectedAddressId === address.id && styles.addressOptionSelected,
                        ]}
                      >
                        <Ionicons
                          name={selectedAddressId === address.id ? 'radio-button-on' : 'radio-button-off'}
                          size={20}
                          color={selectedAddressId === address.id ? colors.primary.main : colors.text.secondary}
                        />
                        <View style={styles.addressOptionText}>
                          <ThemedText variant="bodyBold" color={colors.text.primary}>
                            {[address.firstName, address.lastName].filter(Boolean).join(' ') || 'Address'}
                          </ThemedText>
                          <ThemedText variant="small" color={colors.text.secondary}>
                            {[address.address1, address.city, address.zip, address.territoryCode]
                              .filter(Boolean)
                              .join(', ')}
                          </ThemedText>
                          {address.isDefault && (
                            <View style={styles.defaultBadge}>
                              <ThemedText variant="small" color={colors.primary.main}>Default</ThemedText>
                            </View>
                          )}
                        </View>
                      </AnimatedPressable>
                    ))}
                    <AnimatedPressable
                      testID="checkout-manage-addresses-button"
                      onPress={() => router.push('/addresses')}
                      scaleTo={0.97}
                      style={styles.linkButton}
                    >
                      <Ionicons name="add-circle-outline" size={16} color={colors.primary.main} />
                      <ThemedText variant="bodyBold" color={colors.primary.main}>Add / Manage Addresses</ThemedText>
                    </AnimatedPressable>
                  </>
                ) : (
                  <>
                    <ThemedText variant="body" color={colors.text.secondary} style={styles.helperText}>
                      You don't have any saved addresses yet.
                    </ThemedText>
                    <Button
                      testID="checkout-add-address-button"
                      label="Add Delivery Address"
                      variant="outline"
                      fullWidth
                      onPress={() => router.push('/addresses')}
                    />
                  </>
                )
              ) : (
                <>
                  <View style={styles.guestAddressRow}>
                    <Ionicons name="information-circle-outline" size={18} color={colors.text.secondary} />
                    <ThemedText variant="body" color={colors.text.secondary} style={styles.helperText}>
                      You're checking out as a guest — enter your delivery address on the next screen.
                    </ThemedText>
                  </View>
                  <AnimatedPressable
                    testID="checkout-sign-in-for-address"
                    onPress={() => router.push('/profile')}
                    scaleTo={0.97}
                    style={styles.linkButton}
                  >
                    <Ionicons name="person-outline" size={16} color={colors.primary.main} />
                    <ThemedText variant="bodyBold" color={colors.primary.main}>Sign in to save your address</ThemedText>
                  </AnimatedPressable>
                </>
              )}
            </SectionCard>

            {/* ── 3. Delivery Info ── */}
            <SectionCard title="Delivery" icon="bicycle-outline">
              <View style={styles.etaRow} testID="checkout-eta">
                <View style={styles.etaBadge}>
                  <Ionicons name="time-outline" size={14} color={colors.primary.main} />
                  <ThemedText variant="small" color={colors.primary.main}>30–45 min</ThemedText>
                </View>
                <ThemedText variant="body" color={colors.text.secondary}>Estimated delivery time</ThemedText>
              </View>

              <ThemedText variant="small" color={colors.text.secondary} style={styles.noteLabel}>
                Delivery instructions (optional)
              </ThemedText>
              <TextInput
                testID="checkout-delivery-note"
                style={styles.noteInput}
                value={deliveryNote}
                onChangeText={setDeliveryNote}
                placeholder="E.g. Leave at door, ring bell..."
                placeholderTextColor={colors.text.secondary}
                multiline
                numberOfLines={2}
                maxLength={200}
              />
            </SectionCard>

            {/* ── CTA ── */}
            <View style={[styles.ctaContainer, { paddingBottom: insets.bottom + spacing.md }]}>
              <View style={styles.ctaTotalRow}>
                <ThemedText variant="body" color={colors.text.secondary}>Grand Total</ThemedText>
                <ThemedText variant="h3" color={colors.primary.main} testID="checkout-grand-total">
                  {symbol}{((displayCart?.total ?? 0) + DELIVERY_FEE).toFixed(2)}
                </ThemedText>
              </View>
              <Button
                testID="checkout-continue-payment-button"
                label={isProceeding ? 'Preparing...' : 'Continue to Payment'}
                fullWidth
                loading={isProceeding}
                onPress={handleProceed}
                style={styles.payButton}
              />
              <View style={styles.secureRow}>
                <Ionicons name="lock-closed-outline" size={12} color={colors.text.secondary} />
                <ThemedText variant="small" color={colors.text.secondary}>
                  Secured by Shopify Payments
                </ThemedText>
              </View>
            </View>
          </ScrollView>
        )}
      </View>
    </KeyboardAvoidingView>
  );
}

/* ── Sub-components ── */

function SectionCard({ title, icon, children }: { title: string; icon: string; children: React.ReactNode }) {
  return (
    <View style={styles.sectionCard}>
      <View style={styles.sectionHeader}>
        <Ionicons name={icon as any} size={18} color={colors.primary.main} />
        <ThemedText variant="h3" color={colors.text.primary}>{title}</ThemedText>
      </View>
      {children}
    </View>
  );
}

function OrderLineRow({ line, symbol }: { line: CartLine; symbol: string }) {
  return (
    <View style={styles.lineRow} testID={`checkout-line-${line.id}`}>
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
        {!!line.variantTitle && (
          <ThemedText variant="small" color={colors.text.inverseSecondary}>{line.variantTitle}</ThemedText>
        )}
        <ThemedText variant="small" color={colors.text.inverseSecondary}>Qty: {line.quantity}</ThemedText>
      </View>
      <ThemedText variant="bodyBold" color={colors.text.inverse}>
        {symbol}{line.lineTotal.toFixed(2)}
      </ThemedText>
    </View>
  );
}

function PriceRow({
  label,
  value,
  testID,
  highlight,
}: {
  label: string;
  value: string;
  testID?: string;
  highlight?: boolean;
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
  sectionCard: {
    backgroundColor: colors.background.surface,
    borderRadius: radius.lg,
    padding: spacing.lg,
    gap: spacing.md,
    ...shadows.soft,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginBottom: spacing.xs,
  },
  divider: {
    height: 1,
    backgroundColor: colors.border.default,
    marginVertical: spacing.xs,
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
    width: 52,
    height: 52,
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
  priceRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  totalRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: spacing.xs,
  },
  addressOption: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.sm,
    borderRadius: radius.md,
    padding: spacing.md,
    borderWidth: 1.5,
    borderColor: colors.border.default,
  },
  addressOptionSelected: {
    borderColor: colors.primary.main,
    backgroundColor: 'rgba(139, 92, 246, 0.08)',
  },
  addressOptionText: {
    flex: 1,
    gap: 2,
  },
  defaultBadge: {
    alignSelf: 'flex-start',
    marginTop: 2,
  },
  linkButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    paddingVertical: spacing.xs,
  },
  helperText: {
    flex: 1,
  },
  guestAddressRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.sm,
  },
  etaRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
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
  noteLabel: {
    marginBottom: spacing.xs,
  },
  noteInput: {
    borderRadius: radius.md,
    backgroundColor: colors.background.base,
    borderWidth: 1,
    borderColor: colors.border.default,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    color: colors.text.primary,
    fontSize: 14,
    minHeight: 64,
    textAlignVertical: 'top',
  },
  ctaContainer: {
    gap: spacing.sm,
    paddingTop: spacing.md,
  },
  ctaTotalRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: spacing.xs,
  },
  payButton: {
    marginTop: spacing.xs,
  },
  secureRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.xs,
  },
  // Issues screen
  issuesContainer: {
    flex: 1,
    paddingHorizontal: spacing.lg,
    gap: spacing.md,
  },
  issueHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginBottom: spacing.xs,
  },
  issueRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.xs,
    backgroundColor: colors.background.surface,
    borderRadius: radius.md,
    padding: spacing.md,
  },
  issueText: {
    flex: 1,
  },
  actionButton: {
    marginTop: spacing.md,
  },
});
