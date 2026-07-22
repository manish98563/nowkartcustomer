import React from 'react';
import { View, ScrollView, StyleSheet } from 'react-native';
import { useRouter } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Animated, { FadeIn } from 'react-native-reanimated';
import { colors, spacing } from '@/src/theme';
import { ThemedText, CategoryGroupSection, CategoryCardSkeleton, EmptyState, ErrorState } from '@/src/shared/components';
import { useAsyncData } from '@/src/shared/hooks';
import { productRepository } from '@/src/repositories';
import { Category } from '@/src/types';

export default function CategoriesScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { data: categoryGroups, isLoading, error, refetch } = useAsyncData(
    () => productRepository.getCategoryGroups(),
    []
  );

  const handleCategoryPress = (category: Category) => {
    router.push(`/collection/${category.handle}`);
  };

  return (
    <View style={[styles.screen, { paddingTop: insets.top + spacing.lg }]} testID="categories-screen">
      <ThemedText variant="h1" color={colors.text.primary} style={styles.title}>
        Categories
      </ThemedText>
      <ScrollView
        contentContainerStyle={[styles.scrollContent, { paddingBottom: insets.bottom + spacing.xl }]}
        showsVerticalScrollIndicator={false}
        testID="categories-scroll-view"
      >
        {isLoading ? (
          <View testID="categories-loading-skeleton">
            {[0, 1, 2].map((row) => (
              <View key={row} style={styles.skeletonRow}>
                {[0, 1, 2, 3].map((c) => (
                  <CategoryCardSkeleton key={c} />
                ))}
              </View>
            ))}
          </View>
        ) : error ? (
          <ErrorState testID="categories-error-state" onRetry={refetch} />
        ) : !categoryGroups || categoryGroups.length === 0 ? (
          <EmptyState
            testID="categories-empty-state"
            iconName="grid-outline"
            title="No categories yet"
            subtitle="Categories will show up here once they're added on Shopify."
          />
        ) : (
          <Animated.View entering={FadeIn.duration(280)}>
            {categoryGroups.map((group) => (
              <CategoryGroupSection
                key={group.groupTitle}
                groupTitle={group.groupTitle}
                categories={group.categories}
                onCategoryPress={handleCategoryPress}
                testID={`categories-group-${group.groupTitle}`}
              />
            ))}
          </Animated.View>
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
  title: {
    marginBottom: spacing.lg,
  },
  scrollContent: {
    paddingBottom: spacing.xl,
  },
  skeletonRow: {
    flexDirection: 'row',
    gap: spacing.md,
    marginBottom: spacing.xl,
  },
});
