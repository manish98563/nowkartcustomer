import React from 'react';
import { Pressable, ViewStyle, StyleProp, GestureResponderEvent } from 'react-native';
import Animated, { useAnimatedStyle, useSharedValue, withSpring } from 'react-native-reanimated';

const AnimatedPressableBase = Animated.createAnimatedComponent(Pressable);

interface AnimatedPressableProps {
  onPress?: (e: GestureResponderEvent) => void;
  onPressIn?: (e: GestureResponderEvent) => void;
  onPressOut?: (e: GestureResponderEvent) => void;
  disabled?: boolean;
  scaleTo?: number;
  style?: StyleProp<ViewStyle>;
  testID?: string;
  hitSlop?: { top?: number; bottom?: number; left?: number; right?: number };
  children: React.ReactNode;
}

/**
 * Shared press-feedback wrapper used by every tappable component
 * (buttons, cards, icon buttons, tab items) to give the app a
 * consistent, premium tactile "spring squeeze" on press.
 *
 * Uses `Animated.createAnimatedComponent(Pressable)` so the caller's
 * `style` (layout, flex, sizing, background, etc.) and the animated
 * transform live on the SAME element — avoiding the classic bug where
 * wrapping in an extra inner Animated.View drops layout props like
 * `flex: 1` on the outer Pressable.
 */
export function AnimatedPressable({
  onPress,
  onPressIn,
  onPressOut,
  disabled,
  scaleTo = 0.96,
  style,
  testID,
  hitSlop,
  children,
}: AnimatedPressableProps) {
  const scale = useSharedValue(1);

  const animatedStyle = useAnimatedStyle(() => ({
    transform: [{ scale: scale.value }],
  }));

  return (
    <AnimatedPressableBase
      testID={testID}
      onPress={onPress}
      disabled={disabled}
      hitSlop={hitSlop}
      style={[style, animatedStyle]}
      onPressIn={(e: GestureResponderEvent) => {
        scale.value = withSpring(scaleTo, { damping: 16, stiffness: 320 });
        onPressIn?.(e);
      }}
      onPressOut={(e: GestureResponderEvent) => {
        scale.value = withSpring(1, { damping: 16, stiffness: 320 });
        onPressOut?.(e);
      }}
    >
      {children}
    </AnimatedPressableBase>
  );
}
