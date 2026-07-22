import React from 'react';
import { View, StyleSheet, ViewStyle } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { radius, spacing } from '@/src/theme';
import { ThemedText } from './ThemedText';

interface PillBadgeProps {
  label: string;
  iconName?: keyof typeof Ionicons.glyphMap;
  style?: ViewStyle;
}

/**
 * Small uppercase eyebrow pill badge, e.g. "⚡ DELIVERED IN MINUTES".
 */
export function PillBadge({ label, iconName, style }: PillBadgeProps) {
  return (
    <View style={[styles.container, style]} testID="pill-badge">
      {iconName && <Ionicons name={iconName} size={12} color="#FFFFFF" />}
      <ThemedText variant="eyebrow" color="#FFFFFF">
        {label}
      </ThemedText>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    alignSelf: 'flex-start',
    paddingVertical: spacing.xs + 2,
    paddingHorizontal: spacing.md,
    borderRadius: radius.pill,
    backgroundColor: 'rgba(255, 255, 255, 0.18)',
  },
});
