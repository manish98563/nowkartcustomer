import React from 'react';
import { StyleSheet, View } from 'react-native';
import { Image } from 'expo-image';
import { Ionicons } from '@expo/vector-icons';
import Animated, { FadeInUp } from 'react-native-reanimated';
import { colors, radius, spacing } from '@/src/theme';
import { ThemedText } from './ThemedText';
import { AnimatedPressable } from './AnimatedPressable';
import { Category } from '@/src/types';

interface CategoryCardProps {
  category: Category;
  onPress?: (category: Category) => void;
  index?: number;
  testID?: string;
}

const CARD_SIZE = 78;

/**
 * Light-lavender rounded category card used in the "All Categories" grid.
 * Falls back to a violet basket icon when no product image is available,
 * matching the storefront exactly.
 */
export function CategoryCard({ category, onPress, index, testID }: CategoryCardProps) {
  return (
    <Animated.View entering={typeof index === 'number' ? FadeInUp.delay(index * 50).duration(300) : undefined}>
      <AnimatedPressable
        testID={testID || `category-card-${category.handle}`}
        onPress={() => onPress?.(category)}
        scaleTo={0.94}
        style={styles.container}
      >
        <View style={styles.imageWrap}>
          {category.imageUrl ? (
            <Image source={{ uri: category.imageUrl }} style={styles.image} contentFit="cover" />
          ) : (
            <Ionicons name="basket" size={26} color={colors.primary.main} />
          )}
        </View>
        <ThemedText variant="small" color={colors.text.primary} numberOfLines={2} style={styles.label}>
          {category.title}
        </ThemedText>
      </AnimatedPressable>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  container: {
    width: CARD_SIZE,
    alignItems: 'center',
    gap: spacing.sm,
  },
  imageWrap: {
    width: CARD_SIZE,
    height: CARD_SIZE,
    borderRadius: radius.lg,
    backgroundColor: colors.cards.categoryBg,
    alignItems: 'center',
    justifyContent: 'center',
    overflow: 'hidden',
  },
  image: {
    width: '100%',
    height: '100%',
  },
  label: {
    textAlign: 'center',
  },
});
