import React, { useCallback, useEffect, useState } from 'react';
import { View, ScrollView, StyleSheet, ActivityIndicator } from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Animated, { FadeIn } from 'react-native-reanimated';
import { colors, radius, spacing, shadows } from '@/src/theme';
import { ThemedText, Button, AnimatedPressable, EmptyState, ErrorState, FormField } from '@/src/shared/components';
import { useAuth } from '@/src/features/auth/AuthContext';
import { useShopifySignIn } from '@/src/features/auth/useShopifySignIn';
import { authRepository } from '@/src/repositories';
import { ApiError } from '@/src/services/api/apiClient';
import { Address, AddressInput } from '@/src/types';
import { storeDeliveryAddress } from '@/src/utils/storage/deliveryAddress';

const EMPTY_FORM: AddressInput = {
  firstName: '',
  lastName: '',
  address1: '',
  address2: '',
  city: '',
  zoneCode: '',
  territoryCode: 'GB',
  zip: '',
  phoneNumber: '',
};

type ViewMode = 'list' | 'create' | { edit: Address };

/**
 * Saved delivery addresses — real Shopify Customer Account API data
 * (customer.addresses / customerAddressCreate/Update/Delete), part of the
 * checkout foundation. Guests are prompted to sign in; there is no local
 * guest-only address storage since addresses are customer-account data.
 */
export default function AddressesScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { select } = useLocalSearchParams<{ select?: string }>();
  const isSelectMode = select === '1'; // "Deliver here" picker mode from home screen
  const { isAuthenticated, isRestoring } = useAuth();
  const { signIn, isSigningIn } = useShopifySignIn();

  const [addresses, setAddresses] = useState<Address[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<ViewMode>('list');
  const [form, setForm] = useState<AddressInput>(EMPTY_FORM);
  const [isSaving, setIsSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [signInFeedback, setSignInFeedback] = useState<string | null>(null);

  const loadAddresses = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const profile = await authRepository.getProfile();
      setAddresses(profile.addresses);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not load your addresses.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isAuthenticated) loadAddresses();
  }, [isAuthenticated, loadAddresses]);

  const openCreate = () => {
    setForm(EMPTY_FORM);
    setFormError(null);
    setMode('create');
  };

  const openEdit = (address: Address) => {
    setForm({
      firstName: address.firstName ?? '',
      lastName: address.lastName ?? '',
      address1: address.address1 ?? '',
      address2: address.address2 ?? '',
      city: address.city ?? '',
      zoneCode: address.zoneCode ?? '',
      territoryCode: address.territoryCode ?? 'GB',
      zip: address.zip ?? '',
      phoneNumber: address.phoneNumber ?? '',
    });
    setFormError(null);
    setMode({ edit: address });
  };

  const handleSave = async () => {
    if (!form.address1.trim() || !form.city.trim() || !form.territoryCode.trim()) {
      setFormError('Please fill in address, city, and country.');
      return;
    }
    setIsSaving(true);
    setFormError(null);
    try {
      if (typeof mode === 'object' && 'edit' in mode) {
        await authRepository.updateAddress(mode.edit.id, form);
      } else {
        await authRepository.createAddress(form);
      }
      setMode('list');
      await loadAddresses();
    } catch (e) {
      setFormError(e instanceof ApiError ? e.message : 'Could not save this address.');
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async (address: Address) => {
    try {
      await authRepository.deleteAddress(address.id);
      await loadAddresses();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not delete this address.');
    }
  };

  const handleSignIn = async () => {
    setSignInFeedback(null);
    const result = await signIn();
    if (result.status === 'error' || result.status === 'web-unsupported') {
      setSignInFeedback(result.message ?? 'Could not sign in. Please try again.');
    } else if (result.status === 'success') {
      loadAddresses();
    }
  };

  const handleSelectForDelivery = useCallback(async (address: Address) => {
    await storeDeliveryAddress(address);
    router.back();
  }, [router]);

  const handleBack = () => {
    if (mode !== 'list') {
      setMode('list');
    } else {
      router.back();
    }
  };

  const screenTitle = isSelectMode
    ? 'Select Delivery Address'
    : mode === 'list'
    ? 'Saved Addresses'
    : typeof mode === 'object'
    ? 'Edit Address'
    : 'Add Address';

  return (
    <View style={[styles.screen, { paddingTop: insets.top + spacing.lg }]} testID="addresses-screen">
      <AnimatedPressable
        testID="addresses-back-button"
        onPress={handleBack}
        scaleTo={0.94}
        hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
        style={styles.backButton}
      >
        <Ionicons name="chevron-back" size={18} color={colors.text.primary} />
        <ThemedText variant="bodyBold" color={colors.text.primary}>
          Back
        </ThemedText>
      </AnimatedPressable>

      <ThemedText variant="h1" color={colors.text.primary} style={styles.title}>
        {screenTitle}
      </ThemedText>

      {isRestoring ? (
        <ActivityIndicator color={colors.primary.main} />
      ) : !isAuthenticated ? (
        <View testID="addresses-guest-view">
          <EmptyState
            testID="addresses-guest-empty-state"
            iconName="location-outline"
            title="Sign in to save addresses"
            subtitle="Create an account to save delivery addresses for faster checkout."
          />
          {signInFeedback && (
            <ThemedText variant="small" color={colors.text.secondary} style={styles.feedbackText}>
              {signInFeedback}
            </ThemedText>
          )}
          <Button
            testID="addresses-signin-button"
            label="Sign In"
            fullWidth
            loading={isSigningIn}
            onPress={handleSignIn}
            style={styles.signInButton}
          />
        </View>
      ) : mode === 'list' ? (
        <ScrollView
          showsVerticalScrollIndicator={false}
          contentContainerStyle={{ paddingBottom: insets.bottom + spacing.xl }}
          testID="addresses-list"
        >
          {isLoading ? (
            <ActivityIndicator color={colors.primary.main} />
          ) : error ? (
            <ErrorState testID="addresses-error-state" onRetry={loadAddresses} />
          ) : addresses.length === 0 ? (
            <EmptyState
              testID="addresses-empty-state"
              iconName="location-outline"
              title="No saved addresses yet"
              subtitle="Add a delivery address to speed up checkout."
            />
          ) : (
            addresses.map((address) => (
              <Animated.View
                key={address.id}
                entering={FadeIn.duration(250)}
                style={styles.addressCard}
                testID={`address-card-${address.id}`}
              >
                <View style={styles.addressCardHeader}>
                  <ThemedText variant="bodyBold" color={colors.text.primary}>
                    {[address.firstName, address.lastName].filter(Boolean).join(' ') || 'Delivery address'}
                  </ThemedText>
                  {address.isDefault && (
                    <View style={styles.defaultBadge}>
                      <ThemedText variant="small" color={colors.primary.main}>
                        Default
                      </ThemedText>
                    </View>
                  )}
                </View>
                <ThemedText variant="body" color={colors.text.secondary}>
                  {[address.address1, address.address2, address.city, address.zip, address.territoryCode]
                    .filter(Boolean)
                    .join(', ')}
                </ThemedText>
                <View style={styles.addressActions}>
                  {isSelectMode ? (
                    <AnimatedPressable
                      testID={`address-select-delivery-${address.id}`}
                      onPress={() => handleSelectForDelivery(address)}
                      scaleTo={0.94}
                      style={[styles.addressActionButton, styles.deliverHereButton]}
                    >
                      <Ionicons name="location" size={13} color="#FFFFFF" />
                      <ThemedText variant="small" color="#FFFFFF">
                        Deliver here
                      </ThemedText>
                    </AnimatedPressable>
                  ) : (
                    <>
                      <AnimatedPressable
                        testID={`address-edit-${address.id}`}
                        onPress={() => openEdit(address)}
                        scaleTo={0.94}
                        style={styles.addressActionButton}
                      >
                        <ThemedText variant="small" color={colors.primary.main}>
                          Edit
                        </ThemedText>
                      </AnimatedPressable>
                      <AnimatedPressable
                        testID={`address-delete-${address.id}`}
                        onPress={() => handleDelete(address)}
                        scaleTo={0.94}
                        style={styles.addressActionButton}
                      >
                        <ThemedText variant="small" color={colors.status.error}>
                          Delete
                        </ThemedText>
                      </AnimatedPressable>
                    </>
                  )}
                </View>
              </Animated.View>
            ))
          )}
          <Button
            testID="addresses-add-button"
            label="Add New Address"
            variant="outline"
            fullWidth
            onPress={openCreate}
            style={styles.addButton}
          />
        </ScrollView>
      ) : (
        <ScrollView
          showsVerticalScrollIndicator={false}
          contentContainerStyle={{ paddingBottom: insets.bottom + spacing.xl }}
          testID="addresses-form"
        >
          <FormField
            label="First name"
            value={form.firstName ?? ''}
            onChangeText={(t) => setForm((f) => ({ ...f, firstName: t }))}
            testID="address-form-first-name"
          />
          <FormField
            label="Last name"
            value={form.lastName ?? ''}
            onChangeText={(t) => setForm((f) => ({ ...f, lastName: t }))}
            testID="address-form-last-name"
          />
          <FormField
            label="Address line 1"
            value={form.address1}
            onChangeText={(t) => setForm((f) => ({ ...f, address1: t }))}
            required
            testID="address-form-address1"
          />
          <FormField
            label="Address line 2"
            value={form.address2 ?? ''}
            onChangeText={(t) => setForm((f) => ({ ...f, address2: t }))}
            testID="address-form-address2"
          />
          <FormField
            label="City"
            value={form.city}
            onChangeText={(t) => setForm((f) => ({ ...f, city: t }))}
            required
            testID="address-form-city"
          />
          <FormField
            label="County / State"
            value={form.zoneCode ?? ''}
            onChangeText={(t) => setForm((f) => ({ ...f, zoneCode: t }))}
            testID="address-form-zone"
          />
          <FormField
            label="Postcode"
            value={form.zip ?? ''}
            onChangeText={(t) => setForm((f) => ({ ...f, zip: t }))}
            autoCapitalize="characters"
            testID="address-form-zip"
          />
          <FormField
            label="Country code (e.g. GB)"
            value={form.territoryCode}
            onChangeText={(t) => setForm((f) => ({ ...f, territoryCode: t.toUpperCase() }))}
            required
            autoCapitalize="characters"
            testID="address-form-country"
          />
          <FormField
            label="Phone"
            value={form.phoneNumber ?? ''}
            onChangeText={(t) => setForm((f) => ({ ...f, phoneNumber: t }))}
            keyboardType="phone-pad"
            testID="address-form-phone"
          />

          {formError && (
            <ThemedText variant="small" color={colors.status.error} style={styles.feedbackText}>
              {formError}
            </ThemedText>
          )}

          <Button
            testID="address-form-save-button"
            label="Save Address"
            fullWidth
            loading={isSaving}
            onPress={handleSave}
          />
        </ScrollView>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.background.base,
    paddingHorizontal: spacing.lg,
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
    marginBottom: spacing.sm,
  },
  title: {
    marginBottom: spacing.lg,
  },
  feedbackText: {
    marginBottom: spacing.md,
    textAlign: 'center',
  },
  signInButton: {
    marginTop: spacing.md,
  },
  addressCard: {
    backgroundColor: colors.background.surface,
    borderRadius: radius.lg,
    padding: spacing.md,
    marginBottom: spacing.md,
    gap: spacing.xs,
    ...shadows.soft,
  },
  addressCardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  defaultBadge: {
    backgroundColor: colors.overlay.iconButtonBg,
    borderRadius: radius.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
  },
  addressActions: {
    flexDirection: 'row',
    gap: spacing.lg,
    marginTop: spacing.xs,
  },
  addressActionButton: {
    paddingVertical: spacing.xs,
  },
  deliverHereButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    backgroundColor: colors.primary.main,
    borderRadius: radius.pill,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
  },
  addButton: {
    marginTop: spacing.sm,
  },
});
