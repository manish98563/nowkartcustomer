import React, { useState } from 'react';
import { View, ScrollView, StyleSheet } from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { colors, radius, spacing } from '@/src/theme';
import { ThemedText, ProductCard, EmptyState, AnimatedPressable } from '@/src/shared/components';
import { useCart } from '@/src/features/cart/CartContext';
import { useWishlist } from '@/src/features/wishlist/WishlistContext';
import { Product } from '@/src/types';

/**
 * Wishlist screen — reads from the single shared WishlistContext, so it's
 * always in sync with the heart icon on Home/Search/Collection/Product
 * Detail and the Header badge. Persisted locally today (AsyncStorage);
 * architecture is ready to swap in customer-account sync later.
 */
export default function WishlistScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { addItem } = useCart();
  const { items, toggleWishlist } = useWishlist();
  const [addingProductId, setAddingProductId] = useState<string | null>(null);

  const handleAdd = async (product: Product) => {
    const variantId = product.variants[0]?.id;
    if (!variantId) return;
    setAddingProductId(product.id);
    await addItem(variantId, 1);
    setAddingProductId(null);
  };

  return (
    <View style={[styles.screen, { paddingTop: insets.top + spacing.lg }]} testID="wishlist-screen">
      <AnimatedPressable
        testID="wishlist-back-button"
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

      <ThemedText variant="h1" color={colors.text.primary} style={styles.title} testID="wishlist-title">
        Wishlist
      </ThemedText>

      <ScrollView
        contentContainerStyle={[styles.scrollContent, { paddingBottom: insets.bottom + spacing.xl }]}
        showsVerticalScrollIndicator={false}
        testID="wishlist-scroll-view"
      >
        {items.length === 0 ? (
          <EmptyState
            testID="wishlist-empty-state"
            iconName="heart-outline"
            title="Your wishlist is empty"
            subtitle="Tap the heart on any product to save it here for later."
          />
        ) : (
          <View style={styles.grid}>
            {items.map((product, index) => (
              <ProductCard
                key={product.id}
                product={product}
                index={index}
                width={undefined}
                wishlisted
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
