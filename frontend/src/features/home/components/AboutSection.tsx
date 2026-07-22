import React from 'react';
import { View, StyleSheet } from 'react-native';
import { colors, spacing } from '@/src/theme';
import { ThemedText } from '@/src/shared/components/ThemedText';

/**
 * "About Now Kart" footer section shown at the bottom of the Home screen.
 */
export function AboutSection() {
  return (
    <View style={styles.container} testID="about-section">
      <ThemedText variant="eyebrow" color={colors.primary.main}>
        About Now Kart
      </ThemedText>
      <ThemedText variant="body" color={colors.text.secondary} style={styles.body}>
        NowKart delivers snacks, drinks, groceries and Asian foods to your door in minutes across the UK.
      </ThemedText>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    paddingTop: spacing.lg,
    borderTopWidth: 1,
    borderTopColor: colors.border.default,
    gap: spacing.sm,
  },
  body: {
    lineHeight: 20,
  },
});
