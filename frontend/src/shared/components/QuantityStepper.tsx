import React from 'react';
import { View, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors, radius, spacing } from '@/src/theme';
import { ThemedText } from './ThemedText';
import { AnimatedPressable } from './AnimatedPressable';

interface QuantityStepperProps {
  quantity: number;
  onIncrement: () => void;
  onDecrement: () => void;
  testID?: string;
}

/**
 * Pill "- 1 +" quantity stepper used on the product detail screen.
 */
export function QuantityStepper({ quantity, onIncrement, onDecrement, testID = 'quantity-stepper' }: QuantityStepperProps) {
  return (
    <View style={styles.container} testID={testID}>
      <AnimatedPressable
        testID={`${testID}-decrement`}
        onPress={onDecrement}
        scaleTo={0.85}
        style={styles.button}
        hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
      >
        <Ionicons name="remove" size={16} color={colors.text.primary} />
      </AnimatedPressable>
      <ThemedText variant="bodyBold" color={colors.text.primary} style={styles.value} testID={`${testID}-value`}>
        {quantity}
      </ThemedText>
      <AnimatedPressable
        testID={`${testID}-increment`}
        onPress={onIncrement}
        scaleTo={0.85}
        style={styles.button}
        hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
      >
        <Ionicons name="add" size={16} color={colors.text.primary} />
      </AnimatedPressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    backgroundColor: colors.background.surface,
    borderRadius: radius.pill,
    paddingHorizontal: spacing.xs,
  },
  button: {
    width: 40,
    height: 40,
    alignItems: 'center',
    justifyContent: 'center',
  },
  value: {
    minWidth: 28,
    textAlign: 'center',
  },
});
