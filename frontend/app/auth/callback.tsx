import React from 'react';
import { View, StyleSheet, ActivityIndicator } from 'react-native';
import { useRouter } from 'expo-router';
import { colors, spacing } from '@/src/theme';
import { ThemedText } from '@/src/shared/components';

/**
 * Safety-net fallback route only. In this iteration, sign-in is a native-
 * only flow (expo-web-browser's openAuthSessionAsync captures the OAuth
 * redirect directly without ever navigating here) — a real "Web" Customer
 * Account API client isn't registered yet, so web sign-in is intentionally
 * disabled before it would ever reach this URL. This screen exists purely
 * so an unexpected hit to /auth/callback never 404s or crashes the app.
 */
export default function AuthCallbackScreen() {
  const router = useRouter();

  React.useEffect(() => {
    const timer = setTimeout(() => router.replace('/profile'), 1200);
    return () => clearTimeout(timer);
  }, [router]);

  return (
    <View style={styles.screen} testID="auth-callback-screen">
      <ActivityIndicator color={colors.primary.main} />
      <ThemedText variant="body" color={colors.text.secondary} style={styles.text}>
        Finishing sign-in...
      </ThemedText>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.background.base,
    gap: spacing.md,
  },
  text: {
    textAlign: 'center',
  },
});
