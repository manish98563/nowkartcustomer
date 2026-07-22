from typing import List, Optional

from pydantic import BaseModel


class AuthorizeUrlRequest(BaseModel):
    codeChallenge: str
    platform: str = "native"  # "native" (custom scheme) | "web" (https, dev-preview only)
    origin: Optional[str] = None  # required when platform == "web"


class AuthorizeUrlResponse(BaseModel):
    authorizeUrl: str
    state: str
    redirectUri: str


class TokenExchangeRequest(BaseModel):
    code: str
    state: str
    codeVerifier: str
    redirectUri: str


class UserOut(BaseModel):
    id: str
    email: Optional[str] = None
    firstName: Optional[str] = None
    lastName: Optional[str] = None


class SessionOut(BaseModel):
    accessToken: str
    refreshToken: str
    expiresIn: int
    user: UserOut


class RefreshRequest(BaseModel):
    refreshToken: str


class LogoutRequest(BaseModel):
    refreshToken: str


class AddressIn(BaseModel):
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    address1: str
    address2: Optional[str] = None
    city: str
    zoneCode: Optional[str] = None
    territoryCode: str
    zip: Optional[str] = None
    phoneNumber: Optional[str] = None


class AddressOut(BaseModel):
    id: str
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    address1: Optional[str] = None
    address2: Optional[str] = None
    city: Optional[str] = None
    zoneCode: Optional[str] = None
    territoryCode: Optional[str] = None
    zip: Optional[str] = None
    phoneNumber: Optional[str] = None
    isDefault: bool = False


class OrderSummaryOut(BaseModel):
    id: str
    name: str
    processedAt: str
    cancelledAt: Optional[str] = None
    financialStatus: Optional[str] = None
    fulfillmentStatus: Optional[str] = None
    totalPrice: float
    currencyCode: str
    itemCount: int = 0
    thumbnailUrl: Optional[str] = None


class OrderLineItemOut(BaseModel):
    id: str
    title: str
    quantity: int
    imageUrl: Optional[str] = None
    price: float = 0.0
    originalPrice: float = 0.0
    currencyCode: str = "GBP"


class OrderFulfillmentOut(BaseModel):
    id: str
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None


class OrderDetailOut(BaseModel):
    id: str
    name: str
    processedAt: str
    cancelledAt: Optional[str] = None
    cancelReason: Optional[str] = None
    financialStatus: Optional[str] = None
    fulfillmentStatus: Optional[str] = None
    email: Optional[str] = None
    totalPrice: float
    subtotal: Optional[float] = None
    totalTax: Optional[float] = None
    totalShipping: Optional[float] = None
    totalRefunded: Optional[float] = None
    currencyCode: str
    statusPageUrl: Optional[str] = None
    shippingAddress: Optional[AddressOut] = None
    lineItems: List[OrderLineItemOut] = []
    fulfillments: List[OrderFulfillmentOut] = []


class ProfileOut(BaseModel):
    user: UserOut
    addresses: List[AddressOut] = []
    orders: List[OrderSummaryOut] = []
