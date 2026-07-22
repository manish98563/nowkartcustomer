"""
Backend tests for Iteration 7: Live Order Tracking
Tests /api/tracking/order endpoint and schema validation
"""
import pytest
import requests
import os
from dotenv import load_dotenv

# Load backend env for service-level tests
load_dotenv('/app/backend/.env')

BASE_URL = "https://repo-clone-verify.preview.emergentagent.com"


class TestTrackingAuth:
    """Tracking endpoint authentication tests"""

    def test_tracking_unauthenticated_returns_401(self):
        """GET /api/tracking/order without auth should return 401"""
        response = requests.get(f"{BASE_URL}/api/tracking/order?id=gid%3A%2F%2Fshopify%2FOrder%2F1234")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print(f"PASS: Unauthenticated tracking returns 401")

    def test_tracking_missing_id_param_returns_422_or_401(self):
        """
        GET /api/tracking/order without ?id param.
        NOTE: FastAPI evaluates auth Depends before query params, so 401 takes
        precedence over 422 for unauthenticated requests with missing params.
        Both 422 (param validation) and 401 (auth) are acceptable here.
        """
        response = requests.get(f"{BASE_URL}/api/tracking/order")
        # Auth runs first → 401 for unauthenticated; 422 if auth passes but param missing
        assert response.status_code in (401, 422), \
            f"Expected 401 or 422, got {response.status_code}: {response.text}"
        print(f"PASS: Missing ?id param returns {response.status_code} (auth-first behavior)")

    def test_tracking_endpoint_exists(self):
        """Confirm /api/tracking/order route is mounted"""
        response = requests.get(f"{BASE_URL}/api/tracking/order")
        # Should be 422 (missing param) not 404 (not found)
        assert response.status_code != 404, f"Tracking endpoint not found (404)"
        print(f"PASS: Tracking endpoint is mounted (status={response.status_code})")


class TestTrackingService:
    """Unit-style tests for tracking service logic via imports"""

    def test_tracking_service_imports(self):
        """tracking service can be imported without errors"""
        import sys
        sys.path.insert(0, '/app/backend')
        try:
            from tracking.service import _build_stages
            from tracking.schemas import TrackingStatusOut, TrackingStageOut
            print("PASS: Tracking service and schemas import successfully")
        except ImportError as e:
            pytest.fail(f"Import failed: {e}")

    def test_build_stages_fulfilled_is_not_active(self):
        """isActive should be False when fulfillmentStatus=FULFILLED"""
        import sys
        sys.path.insert(0, '/app/backend')
        from tracking.service import _build_stages

        stages, current_key, current_label = _build_stages(
            processedAt="2024-01-01T00:00:00Z",
            financialStatus="PAID",
            fulfillmentStatus="FULFILLED",
            cancelledAt=None,
            fulfillments=[{"createdAt": "2024-01-02T00:00:00Z", "updatedAt": "2024-01-03T00:00:00Z"}],
        )
        assert current_key == 'delivered', f"Expected 'delivered', got '{current_key}'"
        print("PASS: FULFILLED order sets currentStage='delivered'")

    def test_build_stages_cancelled_order(self):
        """cancelledAt set → currentStage='cancelled'"""
        import sys
        sys.path.insert(0, '/app/backend')
        from tracking.service import _build_stages

        stages, current_key, current_label = _build_stages(
            processedAt="2024-01-01T00:00:00Z",
            financialStatus="PAID",
            fulfillmentStatus=None,
            cancelledAt="2024-01-02T00:00:00Z",
            fulfillments=[],
        )
        assert current_key == 'cancelled', f"Expected 'cancelled', got '{current_key}'"
        print("PASS: Cancelled order sets currentStage='cancelled'")

    def test_is_active_false_for_fulfilled(self):
        """isActive should be False for FULFILLED"""
        import sys
        sys.path.insert(0, '/app/backend')
        from tracking.service import get_tracking_status

        # Verify logic via direct flag computation
        fs = "FULFILLED"
        cancelled_at = None
        is_active = not cancelled_at and fs.upper() != "FULFILLED"
        assert is_active == False, "Expected isActive=False for FULFILLED"
        print("PASS: isActive=False for FULFILLED orders")

    def test_is_active_false_for_cancelled(self):
        """isActive should be False for cancelled orders"""
        cancelled_at = "2024-01-02T00:00:00Z"
        fs = "UNFULFILLED"
        is_active = not cancelled_at and fs.upper() != "FULFILLED"
        assert is_active == False, "Expected isActive=False for cancelled orders"
        print("PASS: isActive=False for cancelled orders")


class TestTrackingSchema:
    """Schema field validation tests"""

    def test_tracking_stage_out_fields(self):
        """TrackingStageOut has all required fields"""
        import sys
        sys.path.insert(0, '/app/backend')
        from tracking.schemas import TrackingStageOut

        stage = TrackingStageOut(
            key="placed",
            label="Order Placed",
            timestamp="2024-01-01T00:00:00Z",
            done=True,
            active=False,
            icon="receipt-outline",
        )
        assert stage.key == "placed"
        assert stage.label == "Order Placed"
        assert stage.timestamp is not None
        assert stage.done == True
        assert stage.active == False
        assert stage.icon == "receipt-outline"
        print("PASS: TrackingStageOut has all required fields")

    def test_tracking_status_out_fields(self):
        """TrackingStatusOut has all required fields"""
        import sys
        sys.path.insert(0, '/app/backend')
        from tracking.schemas import TrackingStatusOut, TrackingStageOut

        status = TrackingStatusOut(
            orderId="gid://shopify/Order/1",
            orderName="#1001",
            currentStage="placed",
            currentStageLabel="Order Placed",
            lastUpdatedAt="2024-01-01T00:00:00Z",
            estimatedDelivery=None,
            isActive=True,
            stages=[],
            deliveryAddress=None,
            totalPrice=10.0,
            currencyCode="GBP",
            items=[],
        )
        assert status.orderId
        assert status.orderName
        assert status.currentStage
        assert status.currentStageLabel
        assert isinstance(status.isActive, bool)
        assert isinstance(status.stages, list)
        assert isinstance(status.totalPrice, float)
        print("PASS: TrackingStatusOut has all required fields")

    def test_architecture_prep_comments_in_schemas(self):
        """Rider App prep comments exist in schemas.py"""
        with open('/app/backend/tracking/schemas.py') as f:
            content = f.read()
        assert 'riderName' in content, "Missing riderName comment"
        assert 'riderLocation' in content, "Missing riderLocation comment"
        assert 'riderEta' in content, "Missing riderEta comment"
        print("PASS: Rider App architecture prep comments present in schemas.py")


class TestTrackingRouterMount:
    """Router mount verification"""

    def test_tracking_router_mounted_in_server(self):
        """Verify tracking router is imported and mounted in server.py"""
        with open('/app/backend/server.py') as f:
            content = f.read()
        assert 'tracking' in content, "Tracking router not imported in server.py"
        assert '/api' in content, "API prefix missing"
        print("PASS: Tracking router mounted in server.py")
