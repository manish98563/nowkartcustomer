import React from 'react';
import { View, ScrollView, StyleSheet } from 'react-native';
import { Image } from 'expo-image';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Animated, { FadeInRight } from 'react-native-reanimated';
import { colors, radius, spacing, shadows } from '@/src/theme';
import { ThemedText, AnimatedPressable, QuantityStepper, EmptyState, LoadingSpinner, Button } from '@/src/shared/components';
import { useCart } from '@/src/features/cart/CartContext';
import { CartLine } from '@/src/types';

export default function CartScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { cart, isLoading, updateLineQuantity, removeLine } = useCart();

  return (
    <View style={[styles.screen, { paddingTop: insets.top + spacing.md }]} testID="cart-screen">
      <View style={styles.headerRow}>
        <AnimatedPressable
          testID="cart-back-button"
          onPress={() => router.back()}
          scaleTo={0.94}
          hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
          style={styles.backButton}
        >
          <Ionicons name="chevron-back" size={18} color={colors.text.primary} />
          <ThemedText variant="bodyBold" color={colors.text.primary}>
            Back
          </ThemedText>
        </AnimatedPressable>
      </View>

      <ThemedText variant="h1" color={colors.text.primary} style={styles.title}>
        Your Cart
      </ThemedText>

      {isLoading ? (
        <LoadingSpinner testID="cart-loading-spinner" />
      ) : !cart || cart.lines.length === 0 ? (
        <EmptyState
          testID="cart-empty-state"
          iconName="bag-handle-outline"
          title="Your cart is empty"
          subtitle="Add snacks, drinks and groceries to see them here."
        />
      ) : (
        <ScrollView
          contentContainerStyle={[styles.scrollContent, { paddingBottom: insets.bottom + spacing.xl }]}
          showsVerticalScrollIndicator={false}
          testID="cart-lines-scroll-view"
        >
          {cart.lines.map((line, index) => (
            <CartLineRow
              key={line.id}
              line={line}
              index={index}
              onIncrement={() => updateLineQuantity(line.id, line.quantity + 1)}
              onDecrement={() =>
                line.quantity > 1 ? updateLineQuantity(line.id, line.quantity - 1) : removeLine(line.id)
              }
              onRemove={() => removeLine(line.id)}
            />
          ))}

          <View style={styles.summary} testID="cart-summary">
            <View style={styles.summaryRow}>
              <ThemedText variant="body" color={colors.text.secondary}>
                Subtotal
              </ThemedText>
              <ThemedText variant="bodyBold" color={colors.text.primary} testID="cart-subtotal">
                £{cart.subtotal.toFixed(2)}
              </ThemedText>
            </View>
            <View style={styles.summaryRow}>
              <ThemedText variant="h3" color={colors.text.primary}>
                Total
              </ThemedText>
              <ThemedText variant="h2" color={colors.text.primary} testID="cart-total">
                £{cart.total.toFixed(2)}
              </ThemedText>
            </View>
          </View>

          <Button
            testID="cart-checkout-button"
            label="Proceed to Checkout"
            fullWidth
            onPress={() => router.push(`/checkout/address?cartId=${encodeURIComponent(cart.id)}`)}
            style={styles.checkoutButton}
          />
        </ScrollView>
      )}
    </View>
  );
}

interface CartLineRowProps {
  line: CartLine;
  index: number;
  onIncrement: () => void;
  onDecrement: () => void;
  onRemove: () => void;
}

function CartLineRow({ line, index, onIncrement, onDecrement, onRemove }: CartLineRowProps) {
  return (
    <Animated.View entering={FadeInRight.delay(index * 60).duration(280)} style={styles.lineRow} testID={`cart-line-${line.id}`}>
      <View style={styles.lineImageWrap}>
        {line.imageUrl ? (
          <Image source={{ uri: line.imageUrl }} style={styles.lineImage} contentFit="contain" />
        ) : (
          <Ionicons name="image-outline" size={22} color={colors.text.inverseSecondary} />
        )}
      </View>

      <View style={styles.lineInfo}>
        <ThemedText variant="bodyBold" color={colors.text.primary} numberOfLines={1}>
          {line.title}
        </ThemedText>
        {!!line.variantTitle && (
          <ThemedText variant="small" color={colors.text.secondary}>
            {line.variantTitle}
          </ThemedText>
        )}
        <ThemedText variant="bodyBold" color={colors.primary.main} style={styles.linePrice}>
          £{line.lineTotal.toFixed(2)}
        </ThemedText>
      </View>

      <View style={styles.lineActions}>
        <AnimatedPressable
          testID={`cart-line-${line.id}-remove`}
          onPress={onRemove}
          scaleTo={0.85}
          hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
          style={styles.removeButton}
        >
          <Ionicons name="trash-outline" size={16} color={colors.status.error} />
        </AnimatedPressable>
        <QuantityStepper
          testID={`cart-line-${line.id}-stepper`}
          quantity={line.quantity}
          onIncrement={onIncrement}
          onDecrement={onDecrement}
        />
      </View>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.background.base,
    paddingHorizontal: spacing.lg,
  },
  headerRow: {
    marginBottom: spacing.sm,
  },
  backButton: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    backgroundColor: colors.background.surface,
    borderRadius: radius.pill,
    paddingVertical: spacing.xs + 2,
    paddingHorizontal: spacing.md,
    gap: 2,
  },
  title: {
    marginBottom: spacing.lg,
  },
  scrollContent: {
    gap: spacing.md,
  },
  lineRow: {
    flexDirection: 'row',
    gap: spacing.md,
    backgroundColor: colors.cards.productBg,
    borderRadius: radius.lg,
    padding: spacing.md,
    ...shadows.soft,
  },
  lineImageWrap: {
    width: 64,
    height: 64,
    borderRadius: radius.md,
    backgroundColor: '#FFFFFF',
    alignItems: 'center',
    justifyContent: 'center',
  },
  lineImage: {
    width: '80%',
    height: '80%',
  },
  lineInfo: {
    flex: 1,
    gap: 2,
  },
  linePrice: {
    marginTop: spacing.xs,
  },
  lineActions: {
    alignItems: 'flex-end',
    justifyContent: 'space-between',
  },
  removeButton: {
    width: 28,
    height: 28,
    alignItems: 'center',
    justifyContent: 'center',
  },
  summary: {
    marginTop: spacing.md,
    paddingTop: spacing.lg,
    borderTopWidth: 1,
    borderTopColor: colors.border.default,
    gap: spacing.sm,
  },
  summaryRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  checkoutButton: {
    marginTop: spacing.lg,
  },
});
