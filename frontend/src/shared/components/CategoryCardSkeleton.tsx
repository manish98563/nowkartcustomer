import React from 'react';
import { View, StyleSheet } from 'react-native';
import { radius, spacing } from '@/src/theme';
import { SkeletonBlock } from './SkeletonBlock';

/**
 * Skeleton placeholder matching CategoryCard's exact dimensions.
 */
export function CategoryCardSkeleton() {
  return (
    <View style={styles.container} testID="category-card-skeleton">
      <SkeletonBlock width={78} height={78} borderRadius={radius.lg} />
      <SkeletonBlock width={60} height={12} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    width: 78,
    alignItems: 'center',
    gap: spacing.sm,
  },
});
