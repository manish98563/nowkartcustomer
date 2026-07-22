import React from 'react';
import { StyleSheet, ActivityIndicator, ViewStyle, GestureResponderEvent } from 'react-native';
import { colors, radius, spacing } from '@/src/theme';
import { ThemedText } from './ThemedText';
import { AnimatedPressable } from './AnimatedPressable';

export type ButtonVariant = 'primary' | 'outline' | 'light' | 'ghost';
export type ButtonSize = 'md' | 'lg';

interface ButtonProps {
  label: string;
  onPress?: (e: GestureResponderEvent) => void;
  variant?: ButtonVariant;
  size?: ButtonSize;
  fullWidth?: boolean;
  loading?: boolean;
  disabled?: boolean;
  icon?: React.ReactNode;
  iconPosition?: 'left' | 'right';
  testID?: string;
  style?: ViewStyle;
}

/**
 * Pill-shaped button matching the Now Kart Shopify storefront.
 * variant="primary" -> solid violet CTA (e.g. "Add to cart")
 * variant="outline"  -> violet border pill (e.g. "ADD" on product cards)
 * variant="light"    -> white pill on dark/gradient surfaces (e.g. "Start shopping")
 * variant="ghost"    -> translucent dark pill (e.g. "Back")
 */
export function Button({
  label,
  onPress,
  variant = 'primary',
  size = 'lg',
  fullWidth = false,
  loading = false,
  disabled = false,
  icon,
  iconPosition = 'left',
  testID,
  style,
}: ButtonProps) {
  const isDisabled = disabled || loading;

  return (
    <AnimatedPressable
      testID={testID}
      onPress={onPress}
      disabled={isDisabled}
      scaleTo={0.95}
      hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
      style={[
        styles.base,
        size === 'md' ? styles.md : styles.lg,
        variantStyles[variant],
        fullWidth && styles.fullWidth,
        isDisabled && styles.disabled,
        style,
      ]}
    >
      {loading ? (
        <ActivityIndicator color={variant === 'light' ? colors.text.inverse : '#FFFFFF'} />
      ) : (
        <>
          {icon && iconPosition === 'left' && icon}
          <ThemedText variant="bodyBold" color={textColorForVariant[variant]}>
            {label}
          </ThemedText>
          {icon && iconPosition === 'right' && icon}
        </>
      )}
    </AnimatedPressable>
  );
}

const textColorForVariant: Record<ButtonVariant, string> = {
  primary: '#FFFFFF',
  outline: colors.primary.main,
  light: colors.text.inverse,
  ghost: colors.text.primary,
};

const variantStyles = StyleSheet.create({
  primary: {
    backgroundColor: colors.primary.main,
  },
  outline: {
    backgroundColor: 'transparent',
    borderWidth: 1.5,
    borderColor: colors.primary.main,
  },
  light: {
    backgroundColor: '#FFFFFF',
  },
  ghost: {
    backgroundColor: colors.overlay.iconButtonBg,
  },
});

const styles = StyleSheet.create({
  base: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radius.pill,
    gap: spacing.xs,
  },
  md: {
    paddingVertical: spacing.sm + 2,
    paddingHorizontal: spacing.lg,
    minHeight: 40,
  },
  lg: {
    paddingVertical: spacing.md + 2,
    paddingHorizontal: spacing.xl,
    minHeight: 52,
  },
  fullWidth: {
    width: '100%',
  },
  disabled: {
    opacity: 0.5,
  },
});
