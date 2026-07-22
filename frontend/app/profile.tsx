import React, { useEffect, useState } from 'react';
import { View, ScrollView, StyleSheet, ActivityIndicator } from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Animated, { FadeIn, FadeInDown } from 'react-native-reanimated';
import { colors, radius, spacing, shadows } from '@/src/theme';
import { ThemedText, Button, AnimatedPressable } from '@/src/shared/components';
import { useAuth } from '@/src/features/auth/AuthContext';
import { useShopifySignIn } from '@/src/features/auth/useShopifySignIn';
import { useWishlist } from '@/src/features/wishlist/WishlistContext';

/**
 * Single entry point for account access: guests see Now Kart's sign-in
 * prompt (Shopify Customer Account OAuth2 + PKCE, launched via
 * useShopifySignIn — both "Log In" and "Sign Up" trigger the identical
 * passwordless flow, per product decision), signed-in customers see their
 * profile + account menu. Guests can always dismiss and keep browsing.
 */
export default function ProfileScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { user, isAuthenticated, isRestoring, signOut, refreshProfile } = useAuth();
  const { signIn, isSigningIn } = useShopifySignIn();
  const { count: wishlistCount } = useWishlist();
  const [feedback, setFeedback] = useState<string | null>(null);
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  useEffect(() => {
    if (isAuthenticated) {
      refreshProfile();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAuthenticated]);

  const handleSignIn = async () => {
    setFeedback(null);
    const result = await signIn();
    if (result.status === 'error' || result.status === 'web-unsupported') {
      setFeedback(result.message ?? 'Could not sign in. Please try again.');
    }
  };

  const handleLogout = async () => {
    setIsLoggingOut(true);
    await signOut();
    setIsLoggingOut(false);
  };

  const displayName =
    user?.firstName || user?.lastName ? `${user?.firstName ?? ''} ${user?.lastName ?? ''}`.trim() : 'Now Kart Customer';
  const initial = (user?.firstName?.[0] ?? user?.email?.[0] ?? 'N').toUpperCase();

  return (
    <View style={[styles.screen, { paddingTop: insets.top + spacing.lg }]} testID="profile-screen">
      <AnimatedPressable
        testID="profile-back-button"
        onPress={() => router.back()}
        scaleTo={0.94}
        hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
        style={styles.backButton}
      >
        <Ionicons name="chevron-back" size={18} color={colors.text.primary} />
        <ThemedText variant="bodyBold" color={colors.text.primary}>
          Back
        </ThemedText>
      </AnimatedPressable>

      {isRestoring ? (
        <View style={styles.centered}>
          <ActivityIndicator color={colors.primary.main} />
        </View>
      ) : isAuthenticated && user ? (
        <ScrollView
          showsVerticalScrollIndicator={false}
          contentContainerStyle={{ paddingBottom: insets.bottom + spacing.xl }}
          testID="profile-authenticated-view"
        >
          <Animated.View entering={FadeIn.duration(300)} style={styles.profileCard} testID="profile-card">
            <View style={styles.avatar}>
              <ThemedText variant="h2" color="#FFFFFF">
                {initial}
              </ThemedText>
            </View>
            <ThemedText variant="h3" color={colors.text.primary} style={styles.profileName} testID="profile-name">
              {displayName}
            </ThemedText>
            {!!user.email && (
              <ThemedText variant="body" color={colors.text.secondary} testID="profile-email">
                {user.email}
              </ThemedText>
            )}
          </Animated.View>

          <Animated.View entering={FadeInDown.duration(300).delay(80)} style={styles.menuGroup}>
            <ProfileMenuRow
              icon="location-outline"
              label="Saved Addresses"
              onPress={() => router.push('/addresses')}
              testID="profile-menu-addresses"
            />
            <ProfileMenuRow
              icon="receipt-outline"
              label="Order History"
              onPress={() => router.push('/orders')}
              testID="profile-menu-orders"
            />
            <ProfileMenuRow
              icon="heart-outline"
              label="Wishlist"
              badgeCount={wishlistCount}
              onPress={() => router.push('/wishlist')}
              testID="profile-menu-wishlist"
              isLast
            />
          </Animated.View>

          <Button
            testID="profile-logout-button"
            label="Log Out"
            variant="outline"
            fullWidth
            loading={isLoggingOut}
            onPress={handleLogout}
            style={styles.logoutButton}
          />
        </ScrollView>
      ) : (
        <View style={styles.guestContainer} testID="profile-guest-view">
          <Animated.View entering={FadeIn.duration(300)} style={styles.guestIconWrap}>
            <Ionicons name="person-circle-outline" size={44} color={colors.primary.main} />
          </Animated.View>
          <ThemedText variant="h2" color={colors.text.primary} style={styles.guestTitle}>
            Sign in to Now Kart
          </ThemedText>
          <ThemedText variant="body" color={colors.text.secondary} style={styles.guestSubtitle}>
            We&apos;ll email you a one-time verification code — no password needed.
          </ThemedText>

          {feedback && (
            <View style={styles.feedbackBanner} testID="profile-auth-feedback">
              <Ionicons name="information-circle-outline" size={16} color={colors.text.secondary} />
              <ThemedText variant="small" color={colors.text.secondary} style={styles.feedbackText}>
                {feedback}
              </ThemedText>
            </View>
          )}

          <Button
            testID="profile-login-button"
            label="Log In"
            variant="primary"
            fullWidth
            loading={isSigningIn}
            onPress={handleSignIn}
            style={styles.guestButton}
          />
          <Button
            testID="profile-signup-button"
            label="Sign Up"
            variant="outline"
            fullWidth
            loading={isSigningIn}
            onPress={handleSignIn}
            style={styles.guestButton}
          />

          <AnimatedPressable
            testID="profile-continue-guest"
            onPress={() => router.back()}
            scaleTo={0.97}
            style={styles.guestContinue}
          >
            <ThemedText variant="bodyBold" color={colors.text.secondary}>
              Continue browsing as guest
            </ThemedText>
          </AnimatedPressable>
        </View>
      )}
    </View>
  );
}

interface ProfileMenuRowProps {
  icon: keyof typeof Ionicons.glyphMap;
  label: string;
  onPress: () => void;
  testID?: string;
  badgeCount?: number;
  isLast?: boolean;
}

function ProfileMenuRow({ icon, label, onPress, testID, badgeCount, isLast }: ProfileMenuRowProps) {
  return (
    <AnimatedPressable
      testID={testID}
      onPress={onPress}
      scaleTo={0.98}
      style={[styles.menuRow, !isLast && styles.menuRowDivider]}
    >
      <View style={styles.menuRowLeft}>
        <View style={styles.menuIconWrap}>
          <Ionicons name={icon} size={18} color={colors.primary.main} />
        </View>
        <ThemedText variant="bodyBold" color={colors.text.primary}>
          {label}
        </ThemedText>
      </View>
      <View style={styles.menuRowRight}>
        {typeof badgeCount === 'number' && badgeCount > 0 && (
          <View style={styles.menuBadge} testID={`${testID}-badge`}>
            <ThemedText variant="small" color="#FFFFFF" style={styles.menuBadgeText}>
              {badgeCount}
            </ThemedText>
          </View>
        )}
        <Ionicons name="chevron-forward" size={16} color={colors.text.secondary} />
      </View>
    </AnimatedPressable>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.background.base,
    paddingHorizontal: spacing.lg,
  },
  centered: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  backButton: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    backgroundColor: colors.background.surface,
    borderRadius: radius.pill,
    paddingVertical: spacing.xs + 2,
    paddingHorizontal: spacing.md,
    gap: 2,
    marginBottom: spacing.lg,
  },
  profileCard: {
    alignItems: 'center',
    gap: spacing.xs,
    marginBottom: spacing.xl,
  },
  avatar: {
    width: 72,
    height: 72,
    borderRadius: 36,
    backgroundColor: colors.primary.main,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: spacing.sm,
  },
  profileName: {
    marginTop: spacing.xs,
  },
  menuGroup: {
    backgroundColor: colors.background.surface,
    borderRadius: radius.lg,
    marginBottom: spacing.xl,
    ...shadows.soft,
  },
  menuRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.md,
  },
  menuRowDivider: {
    borderBottomWidth: 1,
    borderBottomColor: colors.border.default,
  },
  menuRowLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  menuRowRight: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
  },
  menuIconWrap: {
    width: 32,
    height: 32,
    borderRadius: radius.md,
    backgroundColor: colors.overlay.iconButtonBg,
    alignItems: 'center',
    justifyContent: 'center',
  },
  menuBadge: {
    minWidth: 18,
    height: 18,
    paddingHorizontal: 3,
    borderRadius: radius.pill,
    backgroundColor: colors.primary.main,
    alignItems: 'center',
    justifyContent: 'center',
  },
  menuBadgeText: {
    fontSize: 10,
    lineHeight: 12,
    fontWeight: '700',
  },
  logoutButton: {
    marginTop: spacing.sm,
  },
  guestContainer: {
    flex: 1,
    alignItems: 'center',
    paddingTop: spacing.xl,
  },
  guestIconWrap: {
    marginBottom: spacing.md,
  },
  guestTitle: {
    textAlign: 'center',
    marginBottom: spacing.xs,
  },
  guestSubtitle: {
    textAlign: 'center',
    marginBottom: spacing.lg,
    paddingHorizontal: spacing.md,
  },
  feedbackBanner: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.xs,
    backgroundColor: colors.background.surface,
    borderRadius: radius.md,
    padding: spacing.md,
    marginBottom: spacing.lg,
    width: '100%',
  },
  feedbackText: {
    flex: 1,
  },
  guestButton: {
    marginBottom: spacing.sm,
    width: '100%',
  },
  guestContinue: {
    marginTop: spacing.md,
    padding: spacing.sm,
  },
});
