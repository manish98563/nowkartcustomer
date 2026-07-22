/**
 * Now Kart Design System — Typography scale
 * Uses platform System font (SF Pro on iOS / Roboto on Android) to stay native.
 */
import { Platform } from 'react-native';

export const fontFamily = Platform.select({
  ios: 'System',
  android: 'sans-serif',
  default: 'System',
});

export const typography = {
  h1: { fontSize: 32, fontWeight: '800' as const, lineHeight: 38, letterSpacing: -0.5 },
  h2: { fontSize: 24, fontWeight: '700' as const, lineHeight: 32, letterSpacing: -0.3 },
  h3: { fontSize: 18, fontWeight: '700' as const, lineHeight: 24, letterSpacing: -0.2 },
  body: { fontSize: 14, fontWeight: '400' as const, lineHeight: 20, letterSpacing: 0 },
  bodyBold: { fontSize: 14, fontWeight: '600' as const, lineHeight: 20, letterSpacing: 0 },
  small: { fontSize: 12, fontWeight: '500' as const, lineHeight: 16, letterSpacing: 0 },
  eyebrow: {
    fontSize: 10,
    fontWeight: '700' as const,
    lineHeight: 12,
    letterSpacing: 1.5,
    textTransform: 'uppercase' as const,
  },
} as const;

export type TypographyVariant = keyof typeof typography;
