import React from 'react';
import { StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import Animated, { FadeIn, ZoomIn } from 'react-native-reanimated';
import { colors, spacing } from '@/src/theme';
import { ThemedText } from './ThemedText';
import { Button } from './Button';

interface ErrorStateProps {
  title?: string;
  subtitle?: string;
  onRetry?: () => void;
  testID?: string;
}

/**
 * Error state shown when a live Shopify data request fails
 * (network issue, Shopify API error, etc.), with a Retry action.
 */
export function ErrorState({
  title = 'Something went wrong',
  subtitle = "We couldn't load this right now. Please try again.",
  onRetry,
  testID = 'error-state',
}: ErrorStateProps) {
  return (
    <Animated.View entering={FadeIn.duration(300)} style={styles.container} testID={testID}>
      <Animated.View entering={ZoomIn.duration(280)} style={styles.iconWrap}>
        <Ionicons name="cloud-offline-outline" size={28} color={colors.status.error} />
      </Animated.View>
      <ThemedText variant="h3" color={colors.text.primary} style={styles.title}>
        {title}
      </ThemedText>
      <ThemedText variant="body" color={colors.text.secondary} style={styles.subtitle}>
        {subtitle}
      </ThemedText>
      {onRetry && (
        <Button testID={`${testID}-retry-button`} label="Try again" variant="outline" onPress={onRetry} style={styles.retryButton} />
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
  retryButton: {
    marginTop: spacing.md,
  },
});
