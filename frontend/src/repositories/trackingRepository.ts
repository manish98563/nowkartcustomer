import { apiClient } from '@/src/services/api/apiClient';
import { TrackingStatus } from '@/src/types';

/**
 * Tracking repository — the single data-access point for the
 * /api/tracking/* endpoints.
 *
 * ARCHITECTURE PREP:
 * When the Rider App is built, new methods will be added here
 * (e.g. subscribeToRiderLocation, getRiderEta) without changing
 * getTrackingStatus's signature.
 */
export const trackingRepository = {
  /** Fetch live tracking status for an order (uses ?id= to safely pass Shopify GIDs). */
  getTrackingStatus: (orderId: string): Promise<TrackingStatus> =>
    apiClient.get<TrackingStatus>(`/tracking/order?id=${encodeURIComponent(orderId)}`),
};
