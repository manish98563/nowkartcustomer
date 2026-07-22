import React from 'react';
import { StyleSheet, View } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import Animated, { FadeIn } from 'react-native-reanimated';
import { colors, radius, spacing } from '@/src/theme';
import { ThemedText } from '@/src/shared/components/ThemedText';
import { PillBadge } from '@/src/shared/components/PillBadge';
import { Button } from '@/src/shared/components/Button';

interface HeroBannerProps {
  onStartShoppingPress?: () => void;
}

/**
 * Home screen hero: gradient card, "Delivered in minutes" badge, headline,
 * subtext and the light "Start shopping" pill CTA.
 */
export function HeroBanner({ onStartShoppingPress }: HeroBannerProps) {
  return (
    <Animated.View entering={FadeIn.duration(400)}>
      <LinearGradient
        testID="hero-banner"
        colors={[colors.primary.gradientStart, colors.primary.gradientEnd]}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={styles.container}
      >
        <View style={styles.glow} pointerEvents="none" />
        <PillBadge label="Delivered in minutes" iconName="flash" />
        <ThemedText variant="h1" color="#FFFFFF" style={styles.title}>
          Snacks. Drinks. Delivered fast.
        </ThemedText>
        <ThemedText variant="body" color="rgba(255,255,255,0.85)" style={styles.subtitle}>
          Free delivery on local orders. Shop UK favourites and Asian imports in one place.
        </ThemedText>
        <Button
          testID="hero-start-shopping-button"
          label="Start shopping"
          variant="light"
          size="md"
          onPress={onStartShoppingPress}
          icon={<Ionicons name="chevron-forward" size={16} color={colors.text.inverse} />}
          iconPosition="right"
          style={styles.cta}
        />
      </LinearGradient>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  container: {
    borderRadius: radius.xl,
    padding: spacing.xl,
    gap: spacing.md,
    overflow: 'hidden',
  },
  glow: {
    position: 'absolute',
    top: -60,
    right: -40,
    width: 160,
    height: 160,
    borderRadius: 999,
    backgroundColor: 'rgba(255, 255, 255, 0.12)',
  },
  title: {
    marginTop: spacing.xs,
  },
  subtitle: {
    marginBottom: spacing.xs,
  },
  cta: {
    alignSelf: 'flex-start',
  },
});
