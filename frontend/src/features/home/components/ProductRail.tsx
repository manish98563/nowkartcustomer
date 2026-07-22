import React from 'react';
import { View, FlatList, StyleSheet } from 'react-native';
import { spacing } from '@/src/theme';
import { SectionHeader } from '@/src/shared/components/SectionHeader';
import { ProductCard } from '@/src/shared/components/ProductCard';
import { Product } from '@/src/types';

interface ProductRailProps {
  title: string;
  products: Product[];
  onViewAllPress?: () => void;
  onProductPress?: (product: Product) => void;
  onAdd?: (product: Product) => void;
  onToggleWishlist?: (product: Product) => void;
  wishlistedIds?: string[];
  addingProductId?: string | null;
  testID?: string;
}

/**
 * Horizontally scrolling row of ProductCards under a SectionHeader,
 * e.g. "Best sellers in Beverages".
 */
export function ProductRail({
  title,
  products,
  onViewAllPress,
  onProductPress,
  onAdd,
  onToggleWishlist,
  wishlistedIds = [],
  addingProductId,
  testID,
}: ProductRailProps) {
  return (
    <View style={styles.container} testID={testID}>
      <SectionHeader title={title} onViewAllPress={onViewAllPress} testID={`${testID}-header`} />
      <FlatList
        data={products}
        keyExtractor={(item) => item.id}
        horizontal
        showsHorizontalScrollIndicator={false}
        decelerationRate="fast"
        contentContainerStyle={styles.listContent}
        renderItem={({ item, index }) => (
          <ProductCard
            product={item}
            index={index}
            wishlisted={wishlistedIds.includes(item.id)}
            isAdding={addingProductId === item.id}
            onPress={onProductPress}
            onAdd={onAdd}
            onToggleWishlist={onToggleWishlist}
          />
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    marginBottom: spacing.xl,
  },
  listContent: {
    gap: spacing.md,
  },
});
