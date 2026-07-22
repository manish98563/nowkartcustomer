import React, { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import Animated, { FadeInUp, FadeOutDown } from 'react-native-reanimated';
import { colors, radius, spacing, shadows } from '@/src/theme';
import { ThemedText } from './ThemedText';
import { AnimatedPressable } from './AnimatedPressable';

interface FreeDeliveryBannerProps {
  bottomOffset?: number;
}

/**
 * Floating "FREE DELIVERY · Local orders only" gradient toast that hovers
 * above the bottom nav, matching the storefront exactly. Dismissible.
 */
export function FreeDeliveryBanner({ bottomOffset = 0 }: FreeDeliveryBannerProps) {
  const [visible, setVisible] = useState(true);

  if (!visible) return null;

  return (
    <Animated.View
      entering={FadeInUp.delay(500).duration(350)}
      exiting={FadeOutDown.duration(220)}
      style={[styles.wrapper, { bottom: bottomOffset }]}
      pointerEvents="box-none"
    >
      <LinearGradient
        colors={[colors.primary.gradientStart, colors.primary.gradientEnd]}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 0 }}
        style={[styles.container, shadows.elevation]}
        pointerEvents="box-none"
      >
        <View style={styles.iconWrap} pointerEvents="none">
          <Ionicons name="car-outline" size={18} color="#FFFFFF" />
        </View>
        <View style={styles.textGroup} pointerEvents="none">
          <ThemedText variant="bodyBold" color="#FFFFFF">
            Free delivery
          </ThemedText>
          <ThemedText variant="small" color="rgba(255,255,255,0.85)">
            Local orders only
          </ThemedText>
        </View>
        <AnimatedPressable
          testID="free-delivery-banner-close"
          onPress={() => setVisible(false)}
          scaleTo={0.8}
          hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
          style={styles.closeBtn}
        >
          <Ionicons name="close" size={16} color="#FFFFFF" />
        </AnimatedPressable>
      </LinearGradient>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  wrapper: {
    position: 'absolute',
    left: spacing.lg,
    right: spacing.lg,
  },
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    borderRadius: radius.pill,
    paddingVertical: spacing.sm + 2,
    paddingHorizontal: spacing.md,
  },
  iconWrap: {
    width: 32,
    height: 32,
    borderRadius: radius.pill,
    backgroundColor: 'rgba(255,255,255,0.2)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  textGroup: {
    flex: 1,
  },
  closeBtn: {
    width: 26,
    height: 26,
    borderRadius: radius.pill,
    backgroundColor: 'rgba(255,255,255,0.2)',
    alignItems: 'center',
    justifyContent: 'center',
  },
});
