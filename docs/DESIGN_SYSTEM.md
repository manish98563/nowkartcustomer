# NOW KART — DESIGN SYSTEM

> Customer App only. Rider/Vendor/Admin apps will have their own design systems.

---

## Brand

| Element | Value |
|---|---|
| **Wordmark** | "NOW" (white) + "KART" (violet `#8B5CF6`) |
| **Icon** | Amber lightning bolt `#FBBF24` |
| **Tagline** | "Delivered in minutes" (eyebrow style) |
| **Aesthetic** | Dark, premium, quick-commerce |

---

## Colors

```
src/theme/colors.ts — single source of truth
DO NOT add colors without finding them in the Shopify storefront.
```

| Token | Hex | Use |
|---|---|---|
| `background.base` | `#0B0710` | Screen background |
| `background.surface` | `#100C18` | Cards, modals |
| `primary.main` | `#8B5CF6` | CTAs, active states, accent |
| `primary.dark` | `#7C3AED` | Pressed state |
| `text.primary` | `#FFFFFF` | Body text on dark bg |
| `text.secondary` | `#A1A1AA` | Muted text, placeholders |
| `text.inverse` | `#18181B` | Text on white product cards |
| `cards.productBg` | `#FFFFFF` | Product card background |
| `cards.categoryBg` | `#F3E8FF` | Category chip background |
| `border.default` | `#27272A` | Dividers, input borders |
| `border.active` | `#8B5CF6` | Focused inputs |
| `status.success` | `#22C55E` | Order confirmed, delivered |
| `status.error` | `#EF4444` | Errors, cancelled |
| `overlay.dark` | `rgba(0,0,0,0.45)` | Modal backdrop |

---

## Typography

```
src/theme/typography.ts — platform system fonts only
iOS: SF Pro   Android: Roboto
Never use @expo-google-fonts packages.
```

| Token | Size | Weight | Use |
|---|---|---|---|
| `h1` | 32px | 800 | Screen titles |
| `h2` | 24px | 700 | Section headers |
| `h3` | 18px | 700 | Card titles, sub-headers |
| `body` | 14px | 400 | Default text |
| `bodyBold` | 14px | 600 | Labels, emphasis |
| `small` | 12px | 500 | Captions, timestamps |
| `eyebrow` | 10px | 700 | UPPERCASE tags, badges |

---

## Spacing

```
src/theme/spacing.ts — 8pt grid system
```

| Token | Value |
|---|---|
| `xs` | 4px |
| `sm` | 8px |
| `md` | 12px |
| `lg` | 16px |
| `xl` | 24px |
| `xxl` | 32px |
| `xxxl` | 48px |

---

## Border Radius

| Token | Value | Use |
|---|---|---|
| `sm` | 8px | Small chips, tags |
| `md` | 12px | Input fields |
| `lg` | 16px | Cards |
| `xl` | 24px | Bottom sheets |
| `pill` | 9999px | Badges, rounded buttons |

---

## Shadows

| Token | Use |
|---|---|
| `shadows.soft` | elevation 4 — standard cards |
| `shadows.elevation` | elevation 8 — modals, floating elements |

---

## Component Inventory

`src/shared/components/` (23 components)

| Component | Purpose |
|---|---|
| `AnimatedPressable` | Press-scale interaction — use instead of `Pressable` |
| `Button` | Primary / secondary CTA |
| `Header` | App header with wordmark, badges, icons |
| `CustomTabBar` | Bottom tab navigator with testIDs |
| `ProductCard` | Square image, 2-line title, add-to-cart |
| `ProductCardSkeleton` | Shimmer loading state for ProductCard |
| `CategoryCard` | Category tile with image |
| `CategoryCardSkeleton` | Shimmer loading state |
| `CategoryGroupSection` | Horizontal scrollable category row |
| `SearchBar` | Debounced search input |
| `DeliverySelector` | Address selector on Home screen |
| `QuantityStepper` | +/- quantity control |
| `PillBadge` | Colored status badge |
| `SectionHeader` | Section title with optional action |
| `SkeletonBlock` | Generic shimmer block |
| `LoadingSpinner` | Full-screen loading state |
| `ErrorState` | Error with retry button (FadeIn animation) |
| `EmptyState` | Empty state with icon |
| `FormField` | Labeled text input with validation |
| `IconButton` | Circular icon button |
| `FreeDeliveryBanner` | Dismissible offer banner |
| `HeroBanner` | Home hero section |
| `ThemedText` | Typography-aware text component |

---

## UI Principles

- **Guest-first**: auth never blocks browsing or cart
- **Skeleton loading**: always use skeleton components for card-grid content — never blank screens
- **Error states**: every data-fetching screen handles loading / error / empty / loaded
- **Touch targets**: minimum 44×44pt (iOS) / 48×48dp (Android)
- **Animations**: `react-native-reanimated` only — no JS-thread animations
- **Tab bar**: always sticky, SafeArea-aware
- **Keyboard**: always use `KeyboardAvoidingView` with `behavior="padding"` (iOS) / `"height"` (Android)
- **Storage**: always use `src/utils/storage/` — never call `expo-secure-store` or `AsyncStorage` directly
