import React, { useState, useCallback } from 'react';
import { View, ScrollView, StyleSheet } from 'react-native';
import { useRouter } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useFocusEffect } from '@react-navigation/native';
import Animated, { FadeIn } from 'react-native-reanimated';
import { colors, spacing } from '@/src/theme';
import {
  Header,
  DeliverySelector,
  SearchBar,
  ThemedText,
  CategoryGroupSection,
  FreeDeliveryBanner,
  CategoryCardSkeleton,
  ProductCardSkeleton,
  SkeletonBlock,
  ErrorState,
} from '@/src/shared/components';
import { useAsyncData } from '@/src/shared/hooks';
import { HeroBanner } from '@/src/features/home/components/HeroBanner';
import { ProductRail } from '@/src/features/home/components/ProductRail';
import { AboutSection } from '@/src/features/home/components/AboutSection';
import { productRepository } from '@/src/repositories';
import { useCart } from '@/src/features/cart/CartContext';
import { useWishlist } from '@/src/features/wishlist/WishlistContext';
import { useAuth } from '@/src/features/auth/AuthContext';
import { Product, Category, Address } from '@/src/types';
import { getStoredDeliveryAddress } from '@/src/utils/storage/deliveryAddress';

export default function HomeScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { addItem } = useCart();
  const { ids: wishlistedIds, toggleWishlist } = useWishlist();
  const { isAuthenticated } = useAuth();
  const { data, isLoading, error, refetch } = useAsyncData(() => productRepository.getHomeSections(), []);

  const [addingProductId, setAddingProductId] = useState<string | null>(null);
  const [deliveryAddress, setDeliveryAddress] = useState<Address | null>(null);

  // Reload the selected delivery address each time the home screen is focused
  // (e.g. after the user picks an address in /addresses?select=1 and navigates back).
  useFocusEffect(
    useCallback(() => {
      getStoredDeliveryAddress().then(setDeliveryAddress);
    }, [])
  );

  const deliveryAddressText = deliveryAddress
    ? [deliveryAddress.address1, deliveryAddress.city].filter(Boolean).join(', ')
    : undefined;

  const handleAdd = async (product: Product) => {
    const variantId = product.variants[0]?.id;
    if (!variantId) return;
    setAddingProductId(product.id);
    await addItem(variantId, 1);
    setAddingProductId(null);
  };

  const handleCategoryPress = (category: Category) => {
    router.push(`/collection/${category.handle}`);
  };

  return (
    <View style={styles.screen} testID="home-screen">
      <Header onCartPress={() => router.push('/cart')} />

      <View style={styles.stickySection}>
        <DeliverySelector
          testID="home-delivery-selector"
          address={deliveryAddressText}
          onPress={() =>
            isAuthenticated
              ? router.push('/addresses?select=1')
              : router.push('/profile')
          }
        />
        <SearchBar
          testID="home-search-bar"
          value=""
          onChangeText={() => {}}
          onPress={() => router.push('/search')}
        />
      </View>

      <ScrollView
        contentContainerStyle={[styles.scrollContent, { paddingBottom: insets.bottom + 104 }]}
        showsVerticalScrollIndicator={false}
        contentInsetAdjustmentBehavior="never"
        testID="home-scroll-view"
      >
        {isLoading ? (
          <View testID="home-loading-skeleton">
            <SkeletonBlock height={188} borderRadius={24} style={styles.heroSkeleton} />
            <SkeletonBlock width={140} height={22} style={styles.sectionTitle} />
            {[0, 1].map((row) => (
              <View key={row} style={styles.skeletonRow}>
                {[0, 1, 2, 3].map((c) => (
                  <CategoryCardSkeleton key={c} />
                ))}
              </View>
            ))}
            <View style={styles.skeletonRow}>
              {[0, 1, 2].map((c) => (
                <ProductCardSkeleton key={c} />
              ))}
            </View>
          </View>
        ) : error ? (
          <ErrorState testID="home-error-state" onRetry={refetch} />
        ) : (
          <Animated.View entering={FadeIn.duration(300)}>
            <HeroBanner onStartShoppingPress={() => router.push('/(tabs)/categories')} />

            {data && data.categoryGroups.length > 0 && (
              <>
                <ThemedText variant="h2" color={colors.text.primary} style={styles.sectionTitle}>
                  All Categories
                </ThemedText>
                {data.categoryGroups.map((group) => (
                  <CategoryGroupSection
                    key={group.groupTitle}
                    groupTitle={group.groupTitle}
                    categories={group.categories}
                    onCategoryPress={handleCategoryPress}
                    testID={`home-category-group-${group.groupTitle}`}
                  />
                ))}
              </>
            )}

            {data?.rails.map((rail) => (
              <ProductRail
                key={rail.title}
                testID={`home-rail-${rail.title}`}
                title={rail.title}
                products={rail.products}
                wishlistedIds={wishlistedIds}
                addingProductId={addingProductId}
                onProductPress={(p) => router.push(`/product/${p.handle}`)}
                onAdd={handleAdd}
                onToggleWishlist={toggleWishlist}
                onViewAllPress={rail.handle ? () => router.push(`/collection/${rail.handle}`) : undefined}
              />
            ))}

            <AboutSection />
          </Animated.View>
        )}
      </ScrollView>

      <FreeDeliveryBanner bottomOffset={56 + insets.bottom + spacing.md} />
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.background.base,
  },
  stickySection: {
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.lg,
    gap: spacing.md,
    backgroundColor: colors.background.base,
  },
  scrollContent: {
    paddingHorizontal: spacing.lg,
  },
  sectionTitle: {
    marginBottom: spacing.lg,
  },
  heroSkeleton: {
    marginBottom: spacing.xl,
  },
  skeletonRow: {
    flexDirection: 'row',
    gap: spacing.md,
    marginBottom: spacing.xl,
  },
});
