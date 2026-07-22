from typing import List, Optional
from pydantic import BaseModel


class SelectedOption(BaseModel):
    name: str
    value: str


class ProductVariantOut(BaseModel):
    id: str
    title: str
    price: float
    compareAtPrice: Optional[float] = None
    currencyCode: str
    availableForSale: bool
    quantityAvailable: Optional[int] = None
    selectedOptions: List[SelectedOption] = []
    imageUrl: Optional[str] = None


class ProductOut(BaseModel):
    id: str
    handle: str
    title: str
    description: str
    price: float
    compareAtPrice: Optional[float] = None
    currencyCode: str
    imageUrl: Optional[str] = None
    images: List[str] = []
    categoryHandle: Optional[str] = None
    categoryTitle: Optional[str] = None
    vendor: Optional[str] = None
    inStock: bool
    variants: List[ProductVariantOut] = []


class CategoryOut(BaseModel):
    id: str
    handle: str
    title: str
    description: Optional[str] = None
    imageUrl: Optional[str] = None
    groupTitle: str = ""


class CategoryGroupOut(BaseModel):
    groupTitle: str
    categories: List[CategoryOut]


class ProductRailOut(BaseModel):
    title: str
    handle: Optional[str] = None
    products: List[ProductOut]


class HomeSectionsOut(BaseModel):
    categoryGroups: List[CategoryGroupOut]
    rails: List[ProductRailOut]


class CartLineOut(BaseModel):
    id: str
    quantity: int
    variantId: str
    productHandle: str
    title: str
    variantTitle: Optional[str] = None
    imageUrl: Optional[str] = None
    price: float
    currencyCode: str
    lineTotal: float
    availableForSale: bool = True
    quantityAvailable: Optional[int] = None


class CartOut(BaseModel):
    id: str
    checkoutUrl: str
    totalQuantity: int
    subtotal: float
    total: float
    totalTax: float = 0.0
    currencyCode: str
    lines: List[CartLineOut] = []


class AddCartLineRequest(BaseModel):
    cartId: str
    variantId: str
    quantity: int = 1


class UpdateCartLineRequest(BaseModel):
    cartId: str
    lineId: str
    quantity: int


class RemoveCartLineRequest(BaseModel):
    cartId: str
    lineId: str


class CreateCartRequest(BaseModel):
    variantId: Optional[str] = None
    quantity: int = 1


class CartNoteUpdateRequest(BaseModel):
    cartId: str
    note: str


class CartLineIssueOut(BaseModel):
    lineId: str
    title: str
    message: str


class PrepareCheckoutRequest(BaseModel):
    cartId: str
    # Optional delivery address to pre-populate in Shopify Checkout.
    # Fields map directly to Shopify Storefront MailingAddressInput.
    deliveryFirstName: Optional[str] = None
    deliveryLastName: Optional[str] = None
    deliveryAddress1: Optional[str] = None
    deliveryAddress2: Optional[str] = None
    deliveryCity: Optional[str] = None
    deliveryTerritoryCode: Optional[str] = None  # ISO 3166-1 alpha-2, e.g. "GB"
    deliveryZip: Optional[str] = None
    deliveryPhone: Optional[str] = None


class CheckoutPrepareOut(BaseModel):
    cart: CartOut
    isValid: bool
    issues: List[CartLineIssueOut] = []
    checkoutUrl: str
