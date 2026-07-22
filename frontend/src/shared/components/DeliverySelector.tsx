import React from 'react';
import { View, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors, radius, spacing } from '@/src/theme';
import { ThemedText } from './ThemedText';
import { AnimatedPressable } from './AnimatedPressable';

interface DeliverySelectorProps {
  address?: string;
  onPress?: () => void;
  testID?: string;
}

/**
 * "DELIVER TO / Set delivery address" pill selector shown under the header.
 */
export function DeliverySelector({
  address,
  onPress,
  testID = 'delivery-selector',
}: DeliverySelectorProps) {
  return (
    <AnimatedPressable
      testID={testID}
      onPress={onPress}
      scaleTo={0.98}
      hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
      style={styles.container}
    >
      <Ionicons name="location" size={16} color={colors.primary.main} />
      <View style={styles.textGroup}>
        <ThemedText variant="eyebrow" color={colors.text.secondary}>
          Deliver to
        </ThemedText>
        <ThemedText variant="bodyBold" color={colors.text.primary}>
          {address || 'Set delivery address'}
        </ThemedText>
      </View>
      <Ionicons name="chevron-down" size={16} color={colors.text.secondary} />
    </AnimatedPressable>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    borderRadius: radius.pill,
    backgroundColor: colors.background.surface,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.lg,
    alignSelf: 'stretch',
  },
  textGroup: {
    flex: 1,
    gap: 2,
  },
});
