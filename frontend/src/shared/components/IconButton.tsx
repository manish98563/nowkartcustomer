import React from 'react';
import { StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors, radius } from '@/src/theme';
import { ThemedText } from './ThemedText';
import { AnimatedPressable } from './AnimatedPressable';

interface IconButtonProps {
  iconName: keyof typeof Ionicons.glyphMap;
  badgeCount?: number;
  onPress?: () => void;
  testID?: string;
  active?: boolean;
}

/**
 * Rounded-square header icon button (wishlist / account / cart) with
 * an optional violet count badge, matching the storefront header.
 */
export function IconButton({ iconName, badgeCount, onPress, testID, active }: IconButtonProps) {
  return (
    <AnimatedPressable
      testID={testID}
      onPress={onPress}
      scaleTo={0.88}
      hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
      style={[styles.container, active && styles.active]}
    >
      <Ionicons name={iconName} size={20} color={colors.text.primary} />
      {typeof badgeCount === 'number' && (
        <View style={styles.badge} testID={`${testID}-badge`}>
          <ThemedText variant="small" color="#FFFFFF" style={styles.badgeText}>
            {badgeCount}
          </ThemedText>
        </View>
      )}
    </AnimatedPressable>
  );
}

const styles = StyleSheet.create({
  container: {
    width: 44,
    height: 44,
    borderRadius: radius.md,
    backgroundColor: colors.background.surface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  active: {
    borderWidth: 1,
    borderColor: colors.border.active,
  },
  badge: {
    position: 'absolute',
    top: -6,
    right: -6,
    minWidth: 18,
    height: 18,
    paddingHorizontal: 3,
    borderRadius: radius.pill,
    backgroundColor: colors.primary.main,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1.5,
    borderColor: colors.background.base,
  },
  badgeText: {
    fontSize: 10,
    lineHeight: 12,
    fontWeight: '700',
  },
});
