import React from 'react';
import { View, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { colors, spacing } from '@/src/theme';
import { ThemedText } from './ThemedText';
import { IconButton } from './IconButton';
import { useCart } from '@/src/features/cart/CartContext';
import { useWishlist } from '@/src/features/wishlist/WishlistContext';

interface HeaderProps {
  /** Optional override — defaults to the live wishlist count so the badge
   * is always in sync everywhere it appears. */
  wishlistCount?: number;
  onWishlistPress?: () => void;
  onAccountPress?: () => void;
  onCartPress?: () => void;
}

/**
 * Sticky top header: "NOWKART" wordmark (NOW white + KART violet) with a
 * lightning bolt accent, tagline, and the wishlist/account/cart icon group.
 * Cart badge count is always the live Shopify cart's total quantity; the
 * wishlist badge is always the live (locally persisted) wishlist count.
 * Account/wishlist icons default to navigating to /profile and /wishlist
 * respectively so every screen gets consistent navigation for free.
 */
export function Header({
  wishlistCount,
  onWishlistPress,
  onAccountPress,
  onCartPress,
}: HeaderProps) {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { cartCount } = useCart();
  const { count: liveWishlistCount } = useWishlist();

  return (
    <View style={[styles.container, { paddingTop: insets.top + spacing.md }]} testID="app-header">
      <View style={styles.row}>
        <View style={styles.logoGroup}>
          <View style={styles.logoRow}>
            <ThemedText variant="h2" color={colors.text.primary} style={styles.logoWeight}>
              NOW
            </ThemedText>
            <ThemedText variant="h2" color={colors.primary.main} style={styles.logoWeight}>
              KART
            </ThemedText>
            <Ionicons name="flash" size={18} color="#FBBF24" style={styles.bolt} />
          </View>
          <ThemedText variant="eyebrow" color={colors.text.secondary}>
            Delivered in minutes
          </ThemedText>
        </View>

        <View style={styles.iconGroup}>
          <IconButton
            testID="header-wishlist-button"
            iconName="heart-outline"
            badgeCount={wishlistCount ?? liveWishlistCount}
            onPress={onWishlistPress ?? (() => router.push('/wishlist'))}
          />
          <IconButton
            testID="header-account-button"
            iconName="person-outline"
            onPress={onAccountPress ?? (() => router.push('/profile'))}
          />
          <IconButton
            testID="header-cart-button"
            iconName="bag-handle-outline"
            badgeCount={cartCount}
            onPress={onCartPress}
          />
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: colors.background.base,
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.lg,
  },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  logoGroup: {
    gap: 3,
  },
  logoRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
  },
  logoWeight: {
    fontWeight: '800',
  },
  bolt: {
    marginLeft: -2,
  },
  iconGroup: {
    flexDirection: 'row',
    gap: spacing.sm,
  },
});
