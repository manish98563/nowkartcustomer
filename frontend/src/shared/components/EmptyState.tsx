import React from 'react';
import { StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import Animated, { FadeIn, ZoomIn } from 'react-native-reanimated';
import { colors, spacing } from '@/src/theme';
import { ThemedText } from './ThemedText';

interface EmptyStateProps {
  title: string;
  subtitle?: string;
  iconName?: keyof typeof Ionicons.glyphMap;
  testID?: string;
}

/**
 * Empty/no-results state, matching the storefront's "No results" search screen.
 */
export function EmptyState({ title, subtitle, iconName = 'search', testID = 'empty-state' }: EmptyStateProps) {
  return (
    <Animated.View entering={FadeIn.duration(350)} style={styles.container} testID={testID}>
      <Animated.View entering={ZoomIn.duration(320)} style={styles.iconWrap}>
        <Ionicons name={iconName} size={28} color={colors.text.secondary} />
      </Animated.View>
      <ThemedText variant="h3" color={colors.text.primary} style={styles.title}>
        {title}
      </ThemedText>
      {subtitle && (
        <ThemedText variant="body" color={colors.text.secondary} style={styles.subtitle}>
          {subtitle}
        </ThemedText>
      )}
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: spacing.xxxl,
    paddingHorizontal: spacing.xl,
    gap: spacing.sm,
  },
  iconWrap: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.background.surface,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: spacing.sm,
  },
  title: {
    textAlign: 'center',
  },
  subtitle: {
    textAlign: 'center',
  },
});
