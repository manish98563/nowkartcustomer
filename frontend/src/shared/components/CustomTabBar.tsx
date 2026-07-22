import React from 'react';
import { View, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { BottomTabBarProps } from '@react-navigation/bottom-tabs';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Animated, { FadeIn } from 'react-native-reanimated';
import { colors, spacing } from '@/src/theme';
import { ThemedText } from './ThemedText';
import { AnimatedPressable } from './AnimatedPressable';

const ICONS: Record<string, { active: keyof typeof Ionicons.glyphMap; inactive: keyof typeof Ionicons.glyphMap }> = {
  index: { active: 'home', inactive: 'home-outline' },
  categories: { active: 'grid', inactive: 'grid-outline' },
  orders: { active: 'cube', inactive: 'cube-outline' },
};

const TEST_IDS: Record<string, string> = {
  index: 'tab-home',
  categories: 'tab-categories',
  orders: 'tab-orders',
};

/**
 * Custom bottom tab bar matching the storefront exactly: icon + label,
 * with a small violet indicator line above the active tab's icon.
 * Built explicitly (instead of relying on the default RN Navigation web
 * tab bar) so every tab reliably exposes a `testID` / `data-testid`.
 */
export function CustomTabBar({ state, descriptors, navigation }: BottomTabBarProps) {
  const insets = useSafeAreaInsets();

  return (
    <View style={[styles.container, { paddingBottom: insets.bottom + spacing.xs, height: 56 + insets.bottom }]}>
      {state.routes.map((route, index) => {
        const isFocused = state.index === index;
        const { options } = descriptors[route.key];
        const label = (options.title ?? route.name) as string;
        const icons = ICONS[route.name] ?? { active: 'ellipse', inactive: 'ellipse-outline' };
        const testID = TEST_IDS[route.name] ?? `tab-${route.name}`;

        const onPress = () => {
          const event = navigation.emit({ type: 'tabPress', target: route.key, canPreventDefault: true });
          if (!isFocused && !event.defaultPrevented) {
            navigation.navigate(route.name);
          }
        };

        return (
          <AnimatedPressable key={route.key} testID={testID} onPress={onPress} scaleTo={0.88} style={styles.tab}>
            {isFocused && (
              <Animated.View
                entering={FadeIn.duration(180)}
                style={styles.activeIndicator}
                testID={`${testID}-active-indicator`}
              />
            )}
            <Ionicons
              name={isFocused ? icons.active : icons.inactive}
              size={23}
              color={isFocused ? colors.primary.main : colors.text.secondary}
            />
            <ThemedText
              variant="small"
              color={isFocused ? colors.primary.main : colors.text.secondary}
              style={styles.label}
            >
              {label}
            </ThemedText>
          </AnimatedPressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    backgroundColor: colors.background.base,
    borderTopWidth: 1,
    borderTopColor: colors.border.default,
    paddingTop: spacing.xs,
  },
  tab: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 3,
  },
  activeIndicator: {
    position: 'absolute',
    top: 0,
    width: 20,
    height: 2.5,
    borderRadius: 2,
    backgroundColor: colors.primary.main,
  },
  label: {
    fontWeight: '600',
  },
});
