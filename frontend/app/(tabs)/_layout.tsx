import React from 'react';
import { Tabs } from 'expo-router';
import { CustomTabBar } from '@/src/shared/components/CustomTabBar';

/**
 * Bottom tab navigator: Home / Categories / Orders — matching the
 * storefront's 3-tab bottom nav exactly. Uses a custom tab bar so every
 * tab reliably renders a `testID` on both native and web.
 */
export default function TabsLayout() {
  return (
    <Tabs
      screenOptions={{ headerShown: false }}
      tabBar={(props) => <CustomTabBar {...props} />}
    >
      <Tabs.Screen name="index" options={{ title: 'Home' }} />
      <Tabs.Screen name="categories" options={{ title: 'Categories' }} />
      <Tabs.Screen name="orders" options={{ title: 'Orders' }} />
    </Tabs>
  );
}
