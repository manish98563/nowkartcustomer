/**
 * Now Kart Design System — Colors
 * Source of truth: Shopify storefront (vcq88p-fj.myshopify.com) + design_guidelines.json
 * DO NOT invent new colors here. Extend only if a new literal color is found on the storefront.
 */

export const colors = {
  background: {
    base: '#0B0710',
    surface: '#100C18',
    surfaceTranslucent: 'rgba(16, 12, 24, 0.85)',
  },
  primary: {
    main: '#8B5CF6',
    dark: '#7C3AED',
    gradientStart: '#9333EA',
    gradientEnd: '#7C3AED',
  },
  text: {
    primary: '#FFFFFF',
    secondary: '#A1A1AA',
    inverse: '#18181B',
    inverseSecondary: '#52525B',
    accent: '#8B5CF6',
  },
  cards: {
    productBg: '#FFFFFF',
    categoryBg: '#F3E8FF',
  },
  border: {
    default: '#27272A',
    active: '#8B5CF6',
  },
  status: {
    success: '#22C55E',
    error: '#EF4444',
  },
  overlay: {
    dark: 'rgba(0, 0, 0, 0.45)',
    iconButtonBg: 'rgba(139, 92, 246, 0.15)',
  },
} as const;

export type Colors = typeof colors;
