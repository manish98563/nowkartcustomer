import React from 'react';
import { View, TextInput, StyleSheet, KeyboardTypeOptions } from 'react-native';
import { colors, radius, spacing } from '@/src/theme';
import { ThemedText } from './ThemedText';

interface FormFieldProps {
  label: string;
  value: string;
  onChangeText: (text: string) => void;
  placeholder?: string;
  keyboardType?: KeyboardTypeOptions;
  autoCapitalize?: 'none' | 'sentences' | 'words' | 'characters';
  testID?: string;
  required?: boolean;
}

/**
 * Labeled text input for simple forms (addresses, checkout). Matches the
 * app's dark surface + rounded-corner language rather than the pill-shaped
 * SearchBar, since these are structured form fields, not search input.
 */
export function FormField({
  label,
  value,
  onChangeText,
  placeholder,
  keyboardType = 'default',
  autoCapitalize = 'sentences',
  testID,
  required,
}: FormFieldProps) {
  return (
    <View style={styles.container}>
      <ThemedText variant="small" color={colors.text.secondary} style={styles.label}>
        {label}
        {required ? ' *' : ''}
      </ThemedText>
      <TextInput
        testID={testID}
        style={styles.input}
        value={value}
        onChangeText={onChangeText}
        placeholder={placeholder}
        placeholderTextColor={colors.text.secondary}
        keyboardType={keyboardType}
        autoCapitalize={autoCapitalize}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    marginBottom: spacing.md,
  },
  label: {
    marginBottom: spacing.xs,
  },
  input: {
    height: 48,
    borderRadius: radius.md,
    backgroundColor: colors.background.surface,
    borderWidth: 1,
    borderColor: colors.border.default,
    paddingHorizontal: spacing.md,
    color: colors.text.primary,
    fontSize: 14,
  },
});
