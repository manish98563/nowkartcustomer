from fastapi import FastAPI, APIRouter
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List
import uuid
from datetime import datetime


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

from shopify_integration.router import router as shopify_router  # noqa: E402  (must import after load_dotenv)
from auth.router import router as auth_router  # noqa: E402
from auth.db import ensure_indexes  # noqa: E402
from tracking.router import router as tracking_router  # noqa: E402
from delivery.router import router as delivery_router  # noqa: E402
from delivery.db import ensure_delivery_indexes  # noqa: E402
from webhooks.router import router as webhooks_router  # noqa: E402
from webhooks.db import ensure_webhook_indexes  # noqa: E402
from rider.router import router as rider_router  # noqa: E402
from rider.db import ensure_rider_indexes  # noqa: E402
from vendor.router import router as vendor_router  # noqa: E402
from vendor.db import ensure_vendor_indexes  # noqa: E402
from admin.rider_router import router as admin_rider_router  # noqa: E402
from admin.vendor_router import router as admin_vendor_router  # noqa: E402
from admin.router import router as admin_auth_router  # noqa: E402
from admin.dashboard_router import router as admin_dashboard_router  # noqa: E402
from admin.store_router import router as admin_store_router  # noqa: E402
from admin.delivery_router import router as admin_delivery_router  # noqa: E402
from admin.db import ensure_admin_indexes  # noqa: E402

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")


# Define Models
class StatusCheck(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class StatusCheckCreate(BaseModel):
    client_name: str

# Add your routes to the router instead of directly to app
@api_router.get("/")
async def root():
    return {"message": "Hello World"}

@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    status_dict = input.dict()
    status_obj = StatusCheck(**status_dict)
    _ = await db.status_checks.insert_one(status_obj.dict())
    return status_obj

@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    status_checks = await db.status_checks.find().to_list(1000)
    return [StatusCheck(**status_check) for status_check in status_checks]

# Include the router in the main app
app.include_router(api_router)
app.include_router(shopify_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(tracking_router, prefix="/api")
app.include_router(delivery_router, prefix="/api")
app.include_router(webhooks_router, prefix="/api")
app.include_router(rider_router, prefix="/api")
app.include_router(admin_rider_router, prefix="/api")
app.include_router(vendor_router, prefix="/api")
app.include_router(admin_vendor_router, prefix="/api")
app.include_router(admin_auth_router, prefix="/api")
app.include_router(admin_dashboard_router, prefix="/api")
app.include_router(admin_store_router, prefix="/api")
app.include_router(admin_delivery_router, prefix="/api")

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()


@app.on_event("startup")
async def startup_event():
    # Auth indexes (existing)
    await ensure_indexes()
    # Delivery module indexes
    await ensure_delivery_indexes()
    # Webhook module indexes
    await ensure_webhook_indexes()
    # Rider module indexes
    await ensure_rider_indexes()
    # Vendor module indexes
    await ensure_vendor_indexes()
    # Admin module indexes + seed default super admin
    await ensure_admin_indexes()
    from admin.service import seed_default_admin
    await seed_default_admin()
    # Seed the default store if it doesn't exist yet
    from delivery.service import get_default_store
    store = await get_default_store()
    logger.info("Default store ready: '%s' (id=%s)", store.get("name"), store.get("_id"))
    logger.info("Now Kart backend startup complete — all indexes created")
