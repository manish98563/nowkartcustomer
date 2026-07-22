import React, { useMemo, useState } from 'react';
import { View, ScrollView, StyleSheet } from 'react-native';
import { Image } from 'expo-image';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Animated, { FadeIn, FadeInDown } from 'react-native-reanimated';
import { colors, radius, spacing, shadows } from '@/src/theme';
import {
  ThemedText,
  Button,
  QuantityStepper,
  AnimatedPressable,
  SkeletonBlock,
  ErrorState,
} from '@/src/shared/components';
import { useAsyncData } from '@/src/shared/hooks';
import { productRepository } from '@/src/repositories';
import { useCart } from '@/src/features/cart/CartContext';
import { useWishlist } from '@/src/features/wishlist/WishlistContext';
import { ProductVariant } from '@/src/types';

export default function ProductDetailScreen() {
  const { handle } = useLocalSearchParams<{ handle: string }>();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { addItem } = useCart();
  const { isWishlisted, toggleWishlist } = useWishlist();

  const { data: product, isLoading, error, errorStatus, refetch } = useAsyncData(
    () => productRepository.getProductByHandle(handle ?? ''),
    [handle]
  );

  const [quantity, setQuantity] = useState(1);
  const [selectedVariantId, setSelectedVariantId] = useState<string | null>(null);
  const [isAddingToCart, setIsAddingToCart] = useState(false);
  const wishlisted = product ? isWishlisted(product.id) : false;

  const selectedVariant: ProductVariant | undefined = useMemo(() => {
    if (!product) return undefined;
    if (selectedVariantId) return product.variants.find((v) => v.id === selectedVariantId);
    return product.variants[0];
  }, [product, selectedVariantId]);

  const hasMultipleVariants = (product?.variants.length ?? 0) > 1;
  const price = selectedVariant?.price ?? product?.price ?? 0;
  const total = (price * quantity).toFixed(2);
  const isOutOfStock = selectedVariant ? !selectedVariant.availableForSale : product ? !product.inStock : false;

  const handleAddToCart = async () => {
    if (!selectedVariant || isOutOfStock) return;
    setIsAddingToCart(true);
    await addItem(selectedVariant.id, quantity);
    setIsAddingToCart(false);
  };

  const isNotFound = errorStatus === 404 || (!isLoading && !product && !error);

  if (isNotFound) {
    return (
      <View style={[styles.screenPadded, { paddingTop: insets.top + spacing.lg }]} testID="product-not-found">
        <AnimatedPressable
          testID="product-not-found-back-button"
          onPress={() => router.back()}
          scaleTo={0.94}
          style={styles.backButtonInline}
          hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
        >
          <Ionicons name="chevron-back" size={18} color={colors.text.primary} />
          <ThemedText variant="bodyBold" color={colors.text.primary}>
            Back
          </ThemedText>
        </AnimatedPressable>
        <View style={styles.notFoundBody}>
          <Ionicons name="basket-outline" size={40} color={colors.text.secondary} />
          <ThemedText variant="h2" color={colors.text.primary} style={styles.notFoundTitle}>
            Product not found
          </ThemedText>
          <ThemedText variant="body" color={colors.text.secondary} style={styles.notFoundSubtitle}>
            This product may have been removed or is no longer available.
          </ThemedText>
        </View>
      </View>
    );
  }

  if (error) {
    return (
      <View style={[styles.screenPadded, { paddingTop: insets.top + spacing.lg }]} testID="product-detail-screen">
        <ErrorState testID="product-detail-error" onRetry={refetch} />
      </View>
    );
  }

  return (
    <View style={[styles.screen, { paddingTop: insets.top + spacing.md }]} testID="product-detail-screen">
      <ScrollView
        contentContainerStyle={[styles.scrollContent, { paddingBottom: insets.bottom + spacing.xl }]}
        showsVerticalScrollIndicator={false}
        testID="product-detail-scroll-view"
      >
        <View style={styles.imageWrap}>
          <AnimatedPressable
            testID="product-back-button"
            onPress={() => router.back()}
            scaleTo={0.94}
            style={styles.backButton}
            hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
          >
            <Ionicons name="chevron-back" size={18} color={colors.text.primary} />
            <ThemedText variant="bodyBold" color={colors.text.primary}>
              Back
            </ThemedText>
          </AnimatedPressable>
          <AnimatedPressable
            testID="product-wishlist-button"
            onPress={() => product && toggleWishlist(product)}
            scaleTo={0.85}
            style={styles.wishlistButton}
            hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
          >
            <Ionicons
              name={wishlisted ? 'heart' : 'heart-outline'}
              size={18}
              color={wishlisted ? colors.primary.main : colors.text.inverseSecondary}
            />
          </AnimatedPressable>
          {isLoading ? (
            <SkeletonBlock width="60%" height="60%" borderRadius={radius.md} />
          ) : (
            <Animated.View entering={FadeIn.duration(300)} style={styles.imageInner}>
              {product?.imageUrl ? (
                <Image source={{ uri: product.imageUrl }} style={styles.image} contentFit="contain" />
              ) : (
                <Ionicons name="image-outline" size={48} color={colors.text.inverseSecondary} />
              )}
            </Animated.View>
          )}
        </View>

        {isLoading ? (
          <View style={styles.infoSection} testID="product-detail-loading-skeleton">
            <SkeletonBlock width="70%" height={24} />
            <SkeletonBlock width="40%" height={14} />
            <SkeletonBlock width="35%" height={30} />
            <SkeletonBlock width={110} height={36} borderRadius={radius.pill} />
            <SkeletonBlock width="100%" height={52} borderRadius={radius.pill} />
          </View>
        ) : product ? (
          <Animated.View entering={FadeInDown.duration(320)} style={styles.infoSection}>
            <ThemedText variant="h2" color={colors.text.primary} testID="product-title">
              {product.title}
            </ThemedText>
            {!!product.categoryTitle && (
              <ThemedText variant="body" color={colors.text.secondary}>
                {product.categoryTitle}
              </ThemedText>
            )}
            <ThemedText variant="h1" color={colors.text.primary} style={styles.price} testID="product-price">
              £{price.toFixed(2)}
            </ThemedText>

            {hasMultipleVariants && (
              <View style={styles.variantRow} testID="product-variant-selector">
                {product.variants.map((variant) => {
                  const isSelected = selectedVariant?.id === variant.id;
                  return (
                    <AnimatedPressable
                      key={variant.id}
                      testID={`product-variant-${variant.id}`}
                      onPress={() => setSelectedVariantId(variant.id)}
                      scaleTo={0.95}
                      disabled={!variant.availableForSale}
                      style={[
                        styles.variantChip,
                        isSelected && styles.variantChipSelected,
                        !variant.availableForSale && styles.variantChipDisabled,
                      ]}
                    >
                      <ThemedText
                        variant="small"
                        color={isSelected ? '#FFFFFF' : colors.text.primary}
                        style={styles.variantChipLabel}
                      >
                        {variant.title}
                      </ThemedText>
                    </AnimatedPressable>
                  );
                })}
              </View>
            )}

            {isOutOfStock ? (
              <View style={styles.outOfStockBanner} testID="product-out-of-stock-banner">
                <Ionicons name="alert-circle-outline" size={16} color={colors.status.error} />
                <ThemedText variant="bodyBold" color={colors.status.error}>
                  Currently out of stock
                </ThemedText>
              </View>
            ) : (
              <QuantityStepper
                testID="product-quantity-stepper"
                quantity={quantity}
                onIncrement={() => setQuantity((q) => q + 1)}
                onDecrement={() => setQuantity((q) => Math.max(1, q - 1))}
              />
            )}

            <Button
              testID="product-add-to-cart-button"
              label={isOutOfStock ? 'Out of stock' : `Add to cart · £${total}`}
              variant="primary"
              fullWidth
              disabled={isOutOfStock}
              loading={isAddingToCart}
              icon={<Ionicons name="bag-handle-outline" size={16} color="#FFFFFF" />}
              onPress={handleAddToCart}
              style={styles.addToCartButton}
            />

            {!!product.description && (
              <ThemedText variant="body" color={colors.text.secondary} style={styles.description}>
                {product.description}
              </ThemedText>
            )}
          </Animated.View>
        ) : null}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.background.base,
  },
  screenPadded: {
    flex: 1,
    backgroundColor: colors.background.base,
    paddingHorizontal: spacing.lg,
  },
  scrollContent: {
    paddingBottom: spacing.xl,
  },
  backButtonInline: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    backgroundColor: colors.background.surface,
    borderRadius: radius.pill,
    paddingVertical: spacing.xs + 2,
    paddingHorizontal: spacing.md,
    gap: 2,
    marginBottom: spacing.sm,
  },
  notFoundBody: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.sm,
    paddingBottom: spacing.xxxl,
  },
  notFoundTitle: {
    marginTop: spacing.sm,
    textAlign: 'center',
  },
  notFoundSubtitle: {
    textAlign: 'center',
  },
  imageWrap: {
    width: '100%',
    maxWidth: 480,
    aspectRatio: 1,
    alignSelf: 'center',
    backgroundColor: '#FFFFFF',
    borderRadius: radius.xl,
    alignItems: 'center',
    justifyContent: 'center',
    marginHorizontal: spacing.lg,
    marginBottom: spacing.xl,
    overflow: 'hidden',
    ...shadows.elevation,
  },
  imageInner: {
    width: '100%',
    height: '100%',
    alignItems: 'center',
    justifyContent: 'center',
    padding: spacing.xl,
  },
  image: {
    width: '100%',
    height: '100%',
  },
  backButton: {
    position: 'absolute',
    top: spacing.lg,
    left: spacing.lg,
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.overlay.dark,
    borderRadius: radius.pill,
    paddingVertical: spacing.xs + 2,
    paddingHorizontal: spacing.md,
    gap: 2,
    zIndex: 1,
  },
  wishlistButton: {
    position: 'absolute',
    top: spacing.lg,
    right: spacing.lg,
    width: 36,
    height: 36,
    borderRadius: radius.pill,
    backgroundColor: 'rgba(24, 24, 27, 0.06)',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 1,
  },
  infoSection: {
    paddingHorizontal: spacing.lg,
    gap: spacing.md,
  },
  price: {
    marginTop: spacing.xs,
  },
  variantRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
  },
  variantChip: {
    borderWidth: 1.5,
    borderColor: colors.border.default,
    borderRadius: radius.pill,
    paddingVertical: spacing.xs + 2,
    paddingHorizontal: spacing.md,
  },
  variantChipSelected: {
    backgroundColor: colors.primary.main,
    borderColor: colors.primary.main,
  },
  variantChipDisabled: {
    opacity: 0.4,
  },
  variantChipLabel: {
    fontWeight: '600',
  },
  outOfStockBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    alignSelf: 'flex-start',
  },
  addToCartButton: {
    marginTop: spacing.sm,
  },
  description: {
    lineHeight: 20,
    marginTop: spacing.sm,
  },
});
