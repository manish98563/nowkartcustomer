import React, { useEffect, useState } from 'react';
import { View, ScrollView, StyleSheet } from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { colors, spacing } from '@/src/theme';
import {
  ThemedText,
  SearchBar,
  EmptyState,
  ErrorState,
  ProductCard,
  LoadingSpinner,
  AnimatedPressable,
} from '@/src/shared/components';
import { useAsyncData } from '@/src/shared/hooks';
import { productRepository } from '@/src/repositories';
import { useCart } from '@/src/features/cart/CartContext';
import { useWishlist } from '@/src/features/wishlist/WishlistContext';
import { Product } from '@/src/types';

/**
 * Dedicated Search screen — input at top, live Shopify search results
 * below (debounced), "No results" empty state matching the storefront.
 */
export default function SearchScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { addItem } = useCart();
  const { ids: wishlistedIds, toggleWishlist } = useWishlist();
  const [query, setQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [addingProductId, setAddingProductId] = useState<string | null>(null);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(query.trim()), 350);
    return () => clearTimeout(timer);
  }, [query]);

  const { data: results, isLoading, error, refetch } = useAsyncData(
    () => (debouncedQuery ? productRepository.searchProducts(debouncedQuery) : Promise.resolve([])),
    [debouncedQuery]
  );

  const isDebouncing = query.trim().length > 0 && query.trim() !== debouncedQuery;
  const isBusy = isLoading || isDebouncing;

  const handleAdd = async (product: Product) => {
    const variantId = product.variants[0]?.id;
    if (!variantId) return;
    setAddingProductId(product.id);
    await addItem(variantId, 1);
    setAddingProductId(null);
  };

  return (
    <View style={[styles.screen, { paddingTop: insets.top + spacing.md }]} testID="search-screen">
      <View style={styles.headerRow}>
        <AnimatedPressable
          testID="search-back-button"
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
        Search
      </ThemedText>

      <SearchBar testID="search-input-bar" value={query} onChangeText={setQuery} autoFocus />

      <ScrollView
        contentContainerStyle={[styles.results, { paddingBottom: insets.bottom + spacing.xl }]}
        showsVerticalScrollIndicator={false}
        keyboardShouldPersistTaps="handled"
        testID="search-results-scroll-view"
      >
        {query.trim().length === 0 ? null : isBusy ? (
          <LoadingSpinner testID="search-loading-spinner" />
        ) : error ? (
          <ErrorState testID="search-error-state" onRetry={refetch} />
        ) : !results || results.length === 0 ? (
          <EmptyState
            testID="search-no-results"
            title="No results"
            subtitle={`We couldn't find anything for "${query}".`}
          />
        ) : (
          <View style={styles.grid}>
            {results.map((product, index) => (
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
  headerRow: {
    marginBottom: spacing.sm,
  },
  backButton: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    backgroundColor: colors.background.surface,
    borderRadius: 9999,
    paddingVertical: spacing.xs + 2,
    paddingHorizontal: spacing.md,
    gap: 2,
  },
  title: {
    marginBottom: spacing.lg,
  },
  results: {
    paddingTop: spacing.xl,
  },
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.md,
    justifyContent: 'space-between',
  },
});
