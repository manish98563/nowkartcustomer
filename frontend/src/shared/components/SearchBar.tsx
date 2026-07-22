import React, { useEffect, useState } from 'react';
import { TextInput, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import Animated, {
  useAnimatedStyle,
  useSharedValue,
  withTiming,
  interpolateColor,
} from 'react-native-reanimated';
import { colors, radius, spacing } from '@/src/theme';
import { AnimatedPressable } from './AnimatedPressable';

interface SearchBarProps {
  value: string;
  onChangeText: (text: string) => void;
  placeholder?: string;
  editable?: boolean;
  autoFocus?: boolean;
  onPress?: () => void;
  testID?: string;
}

/**
 * Pill search input with a smoothly animated violet border when focused,
 * matching both the home screen (idle/tap-to-navigate) and search screen
 * (typable, active) states.
 */
export function SearchBar({
  value,
  onChangeText,
  placeholder = 'Search for snacks, drinks & more...',
  editable = true,
  autoFocus = false,
  onPress,
  testID = 'search-bar',
}: SearchBarProps) {
  const [focused, setFocused] = useState(false);
  const focusProgress = useSharedValue(0);

  useEffect(() => {
    focusProgress.value = withTiming(focused ? 1 : 0, { duration: 180 });
  }, [focused, focusProgress]);

  const animatedBorderStyle = useAnimatedStyle(() => ({
    borderColor: interpolateColor(focusProgress.value, [0, 1], ['transparent', colors.primary.main]),
  }));

  const content = (
    <>
      <Ionicons name="search" size={18} color={colors.text.secondary} />
      <TextInput
        testID={`${testID}-input`}
        style={styles.input}
        value={value}
        onChangeText={onChangeText}
        placeholder={placeholder}
        placeholderTextColor={colors.text.secondary}
        editable={editable && !onPress}
        autoFocus={autoFocus}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        pointerEvents={onPress ? 'none' : 'auto'}
        returnKeyType="search"
      />
    </>
  );

  if (onPress) {
    return (
      <AnimatedPressable testID={testID} onPress={onPress} scaleTo={0.98} style={[styles.container, animatedBorderStyle]}>
        {content}
      </AnimatedPressable>
    );
  }

  return (
    <Animated.View testID={testID} style={[styles.container, animatedBorderStyle]}>
      {content}
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    height: 48,
    borderRadius: radius.pill,
    backgroundColor: colors.background.surface,
    paddingHorizontal: spacing.lg,
    borderWidth: 1.5,
  },
  input: {
    flex: 1,
    fontSize: 14,
    color: colors.text.primary,
  },
});
