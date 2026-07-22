/**
 * Tracking domain types — the canonical TypeScript interface for order tracking.
 *
 * ARCHITECTURE PREP FOR RIDER APP:
 * When the Rider App is built, add these to TrackingStatus without breaking
 * existing consumers:
 *   riderName?: string | null;
 *   riderPhone?: string | null;
 *   riderLocation?: { lat: number; lng: number; updatedAt: string } | null;
 *   riderEta?: string | null;         // ISO datetime from rider's GPS ETA
 *   trackingUrl?: string | null;      // External courier tracking URL
 *
 * The `isActive` flag is the frontend's signal to start/stop polling.
 */
import { Address } from './auth';
import { OrderLineItem } from './auth';

export interface TrackingStage {
  key: string;          // placed | confirmed | preparing | out_for_delivery | delivered | cancelled
  label: string;
  timestamp?: string | null;
  done: boolean;
  active: boolean;
  icon: string;
}

export interface TrackingStatus {
  orderId: string;
  orderName: string;
  currentStage: string;
  currentStageLabel: string;
  lastUpdatedAt?: string | null;
  estimatedDelivery?: string | null;
  isActive: boolean;            // false = delivered or cancelled — stop polling
  stages: TrackingStage[];
  deliveryAddress?: Address | null;
  totalPrice: number;
  currencyCode: string;
  items: OrderLineItem[];
  // Rider App extension points (not populated until Rider App is built):
  // riderName?: string | null;
  // riderLocation?: { lat: number; lng: number; updatedAt: string } | null;
  // riderEta?: string | null;
}
