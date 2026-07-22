import React from 'react';
import { ActivityIndicator, StyleSheet, View } from 'react-native';
import { Image } from 'expo-image';
import { Ionicons } from '@expo/vector-icons';
import Animated, { FadeInRight } from 'react-native-reanimated';
import { colors, radius, spacing, shadows } from '@/src/theme';
import { ThemedText } from './ThemedText';
import { AnimatedPressable } from './AnimatedPressable';
import { Product } from '@/src/types';

interface ProductCardProps {
  product: Product;
  wishlisted?: boolean;
  isAdding?: boolean;
  onPress?: (product: Product) => void;
  onToggleWishlist?: (product: Product) => void;
  onAdd?: (product: Product) => void;
  width?: number;
  index?: number;
  testID?: string;
}

const DEFAULT_WIDTH = 152;

/**
 * White high-contrast product card used in horizontal rails and grids.
 * Mirrors the storefront: image on white bg, heart overlay, name, price,
 * outline "ADD" pill button. Optionally staggers in on first mount when
 * an `index` is provided (used inside rails/grids).
 */
export function ProductCard({
  product,
  wishlisted = false,
  isAdding = false,
  onPress,
  onToggleWishlist,
  onAdd,
  width = DEFAULT_WIDTH,
  index,
  testID,
}: ProductCardProps) {
  const cardTestID = testID || `product-card-${product.id}`;
  const outOfStock = !product.inStock;

  return (
    <Animated.View
      entering={typeof index === 'number' ? FadeInRight.delay(index * 60).duration(320) : undefined}
    >
      <AnimatedPressable
        testID={cardTestID}
        onPress={() => onPress?.(product)}
        scaleTo={0.97}
        style={[styles.container, { width }]}
      >
        <View style={styles.imageWrap}>
          {product.imageUrl ? (
            <Image source={{ uri: product.imageUrl }} style={styles.image} contentFit="contain" />
          ) : (
            <Ionicons name="image-outline" size={28} color={colors.text.inverseSecondary} />
          )}
          {outOfStock && (
            <View style={styles.outOfStockBadge} testID={`${cardTestID}-out-of-stock`}>
              <ThemedText variant="small" color="#FFFFFF" style={styles.outOfStockLabel}>
                Out of stock
              </ThemedText>
            </View>
          )}
          <AnimatedPressable
            testID={`${cardTestID}-wishlist`}
            onPress={() => onToggleWishlist?.(product)}
            scaleTo={0.8}
            hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
            style={styles.wishlistBtn}
          >
            <Ionicons
              name={wishlisted ? 'heart' : 'heart-outline'}
              size={16}
              color={wishlisted ? colors.primary.main : colors.text.inverseSecondary}
            />
          </AnimatedPressable>
        </View>

        <View style={styles.info}>
          <ThemedText
            variant="bodyBold"
            color={colors.text.inverse}
            numberOfLines={2}
            style={styles.title}
            testID={`${cardTestID}-title`}
          >
            {product.title}
          </ThemedText>

          <View style={styles.footerRow}>
            <ThemedText variant="h3" color={colors.text.inverse}>
              £{product.price.toFixed(2)}
            </ThemedText>
            <AnimatedPressable
              testID={`${cardTestID}-add`}
              onPress={() => !outOfStock && onAdd?.(product)}
              disabled={outOfStock || isAdding}
              scaleTo={0.88}
              hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
              style={[styles.addBtn, outOfStock && styles.addBtnDisabled]}
            >
              {isAdding ? (
                <ActivityIndicator size="small" color={colors.primary.main} />
              ) : (
                <ThemedText
                  variant="small"
                  color={outOfStock ? colors.text.secondary : colors.primary.main}
                  style={styles.addLabel}
                >
                  ADD
                </ThemedText>
              )}
            </AnimatedPressable>
          </View>
        </View>
      </AnimatedPressable>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: colors.cards.productBg,
    borderRadius: radius.lg,
    overflow: 'hidden',
    ...shadows.soft,
  },
  imageWrap: {
    width: '100%',
    height: 120,
    backgroundColor: '#FFFFFF',
    alignItems: 'center',
    justifyContent: 'center',
  },
  image: {
    width: '72%',
    height: '72%',
  },
  wishlistBtn: {
    position: 'absolute',
    top: spacing.sm,
    right: spacing.sm,
    width: 28,
    height: 28,
    borderRadius: radius.pill,
    backgroundColor: 'rgba(24, 24, 27, 0.06)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  info: {
    padding: spacing.md,
    gap: spacing.sm,
  },
  title: {
    // Reserve space for up to 2 lines (bodyBold lineHeight 20) so every card in a
    // row/grid stays the same height whether the title wraps to 1 or 2 lines.
    minHeight: 40,
  },
  footerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  addBtn: {
    borderWidth: 1.2,
    borderColor: colors.primary.main,
    borderRadius: radius.pill,
    paddingVertical: 5,
    paddingHorizontal: spacing.md,
    minWidth: 44,
    alignItems: 'center',
  },
  addBtnDisabled: {
    borderColor: colors.text.secondary,
  },
  addLabel: {
    fontWeight: '700',
    letterSpacing: 0.5,
  },
  outOfStockBadge: {
    position: 'absolute',
    bottom: spacing.sm,
    left: spacing.sm,
    right: spacing.sm,
    backgroundColor: colors.overlay.dark,
    borderRadius: radius.sm,
    paddingVertical: 3,
    alignItems: 'center',
  },
  outOfStockLabel: {
    fontWeight: '700',
  },
});
