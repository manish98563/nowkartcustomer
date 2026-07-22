import React from 'react';
import { View, StyleSheet } from 'react-native';
import { colors, spacing } from '@/src/theme';
import { ThemedText } from './ThemedText';
import { CategoryCard } from './CategoryCard';
import { Category } from '@/src/types';

interface CategoryGroupSectionProps {
  groupTitle: string;
  categories: Category[];
  onCategoryPress?: (category: Category) => void;
  testID?: string;
}

/**
 * A titled group of category cards laid out in a 4-column wrapping grid,
 * used on both the Home ("All Categories") and Categories screens.
 */
export function CategoryGroupSection({ groupTitle, categories, onCategoryPress, testID }: CategoryGroupSectionProps) {
  return (
    <View style={styles.container} testID={testID}>
      <ThemedText variant="h3" color={colors.text.primary} style={styles.title}>
        {groupTitle}
      </ThemedText>
      <View style={styles.grid}>
        {categories.map((category, index) => (
          <CategoryCard key={category.id} category={category} index={index} onPress={onCategoryPress} />
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    marginBottom: spacing.xl,
  },
  title: {
    marginBottom: spacing.md,
  },
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.md,
  },
});
