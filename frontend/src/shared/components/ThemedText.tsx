import React from 'react';
import { Text, TextProps, StyleSheet } from 'react-native';
import { colors, typography, TypographyVariant } from '@/src/theme';

interface ThemedTextProps extends TextProps {
  variant?: TypographyVariant;
  color?: string;
  children: React.ReactNode;
}

/**
 * Every piece of text in the app MUST go through this component so the
 * typography scale + font settings stay centralized and consistent.
 */
export function ThemedText({
  variant = 'body',
  color = colors.text.primary,
  style,
  children,
  ...rest
}: ThemedTextProps) {
  return (
    <Text
      style={[styles.base, typography[variant], { color }, style]}
      maxFontSizeMultiplier={1.3}
      {...rest}
    >
      {children}
    </Text>
  );
}

const styles = StyleSheet.create({
  base: {
    fontFamily: undefined,
  },
});
