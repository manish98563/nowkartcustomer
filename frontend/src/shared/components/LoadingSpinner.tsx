import React from 'react';
import { View, ActivityIndicator, StyleSheet } from 'react-native';
import { colors, spacing } from '@/src/theme';
import { ThemedText } from './ThemedText';

interface LoadingSpinnerProps {
  label?: string;
  fullscreen?: boolean;
  testID?: string;
}

/**
 * Centered violet activity indicator used for screen/section loading states.
 */
export function LoadingSpinner({ label, fullscreen = false, testID = 'loading-spinner' }: LoadingSpinnerProps) {
  return (
    <View style={[styles.container, fullscreen && styles.fullscreen]} testID={testID}>
      <ActivityIndicator size="large" color={colors.primary.main} />
      {label && (
        <ThemedText variant="body" color={colors.text.secondary} style={styles.label}>
          {label}
        </ThemedText>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: spacing.xxl,
    gap: spacing.md,
  },
  fullscreen: {
    flex: 1,
    backgroundColor: colors.background.base,
  },
  label: {
    marginTop: spacing.xs,
  },
});
