import React, { useState } from 'react';
import { View, ScrollView, StyleSheet } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { colors, radius, spacing } from '@/src/theme';
import {
  ThemedText,
  ProductCard,
  ProductCardSkeleton,
  EmptyState,
  ErrorState,
  AnimatedPressable,
} from '@/src/shared/components';
import { useAsyncData } from '@/src/shared/hooks';
import { productRepository } from '@/src/repositories';
import { useCart } from '@/src/features/cart/CartContext';
import { useWishlist } from '@/src/features/wishlist/WishlistContext';
import { Product } from '@/src/types';

export default function CollectionScreen() {
  const { handle } = useLocalSearchParams<{ handle: string }>();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { addItem } = useCart();
  const { ids: wishlistedIds, toggleWishlist } = useWishlist();

  const { data, isLoading, error, refetch } = useAsyncData(
    () => productRepository.getCollectionProducts(handle ?? ''),
    [handle]
  );

  const [addingProductId, setAddingProductId] = useState<string | null>(null);

  const handleAdd = async (product: Product) => {
    const variantId = product.variants[0]?.id;
    if (!variantId) return;
    setAddingProductId(product.id);
    await addItem(variantId, 1);
    setAddingProductId(null);
  };

  return (
    <View style={[styles.screen, { paddingTop: insets.top + spacing.md }]} testID="collection-screen">
      <AnimatedPressable
        testID="collection-back-button"
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

      <ThemedText variant="h1" color={colors.text.primary} style={styles.title} testID="collection-title">
        {data?.collection.title ?? ' '}
      </ThemedText>

      <ScrollView
        contentContainerStyle={[styles.scrollContent, { paddingBottom: insets.bottom + spacing.xl }]}
        showsVerticalScrollIndicator={false}
        testID="collection-scroll-view"
      >
        {isLoading ? (
          <View style={styles.grid} testID="collection-loading-skeleton">
            {[0, 1, 2, 3].map((c) => (
              <ProductCardSkeleton key={c} />
            ))}
          </View>
        ) : error ? (
          <ErrorState testID="collection-error-state" onRetry={refetch} />
        ) : !data || data.products.length === 0 ? (
          <EmptyState
            testID="collection-empty-state"
            iconName="basket-outline"
            title="No products yet"
            subtitle="This category doesn't have any products right now."
          />
        ) : (
          <View style={styles.grid}>
            {data.products.map((product, index) => (
              <ProductCard
                key={product.id}
                product={product}
                index={index}
                width={undefined}
                wishlisted={wishlistedIds.includes(product.id)}
                isAdding={addingProductId === product.id}
                onPress={(p) => router.push(`/product/${p.handle}`)}
                onAdd={handleAdd}
                onToggleWishlist={toggleWishlist}
              />
            ))}
          </View>
        )}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.background.base,
    paddingHorizontal: spacing.lg,
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
    marginBottom: spacing.sm,
  },
  title: {
    marginBottom: spacing.lg,
  },
  scrollContent: {
    paddingBottom: spacing.xl,
  },
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.md,
    justifyContent: 'space-between',
  },
});
