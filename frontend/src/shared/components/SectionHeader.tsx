import React from 'react';
import { View, TouchableOpacity, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors, spacing } from '@/src/theme';
import { ThemedText } from './ThemedText';

interface SectionHeaderProps {
  title: string;
  onViewAllPress?: () => void;
  testID?: string;
}

/**
 * "Section title" + optional "View all >" link, used above product rails
 * and category groups.
 */
export function SectionHeader({ title, onViewAllPress, testID }: SectionHeaderProps) {
  return (
    <View style={styles.container} testID={testID}>
      <ThemedText variant="h3" color={colors.text.primary}>
        {title}
      </ThemedText>
      {onViewAllPress && (
        <TouchableOpacity
          testID={`${testID}-view-all`}
          onPress={onViewAllPress}
          style={styles.viewAll}
          hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
        >
          <ThemedText variant="bodyBold" color={colors.primary.main}>
            View all
          </ThemedText>
          <Ionicons name="chevron-forward" size={14} color={colors.primary.main} />
        </TouchableOpacity>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: spacing.md,
  },
  viewAll: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 2,
  },
});
