import React from 'react';
import { View, StyleSheet } from 'react-native';
import { radius, spacing, shadows } from '@/src/theme';
import { SkeletonBlock } from './SkeletonBlock';

interface ProductCardSkeletonProps {
  width?: number;
}

/**
 * Skeleton placeholder matching ProductCard's exact dimensions,
 * shown briefly while "loading" home/category/search content.
 */
export function ProductCardSkeleton({ width = 152 }: ProductCardSkeletonProps) {
  return (
    <View style={[styles.container, { width }]} testID="product-card-skeleton">
      <SkeletonBlock width="100%" height={110} borderRadius={0} />
      <View style={styles.info}>
        <SkeletonBlock width="80%" height={14} />
        <View style={styles.footerRow}>
          <SkeletonBlock width={50} height={18} />
          <SkeletonBlock width={44} height={22} borderRadius={radius.pill} />
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: '#FFFFFF',
    borderRadius: radius.lg,
    overflow: 'hidden',
    ...shadows.soft,
  },
  info: {
    padding: spacing.md,
    gap: spacing.sm,
  },
  footerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
});
