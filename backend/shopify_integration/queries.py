"""Raw GraphQL query/mutation strings for the Shopify Storefront API."""

PRODUCT_FIELDS = """
  id
  handle
  title
  description
  productType
  vendor
  featuredImage {
    url
    altText
  }
  images(first: 6) {
    nodes {
      url
      altText
    }
  }
  priceRange {
    minVariantPrice { amount currencyCode }
  }
  compareAtPriceRange {
    minVariantPrice { amount currencyCode }
  }
  availableForSale
  variants(first: 25) {
    nodes {
      id
      title
      availableForSale
      quantityAvailable
      price { amount currencyCode }
      compareAtPrice { amount currencyCode }
      selectedOptions { name value }
      image { url altText }
    }
  }
"""

COLLECTIONS_QUERY = """
query Collections($first: Int!) {
  collections(first: $first) {
    nodes {
      id
      handle
      title
      description
      image {
        url
        altText
      }
    }
  }
}
"""

COLLECTION_PRODUCTS_QUERY = f"""
query CollectionProducts($handle: String!, $first: Int!, $sortKey: ProductCollectionSortKeys, $reverse: Boolean) {{
  collection(handle: $handle) {{
    id
    handle
    title
    description
    image {{ url altText }}
    products(first: $first, sortKey: $sortKey, reverse: $reverse) {{
      nodes {{
        {PRODUCT_FIELDS}
      }}
    }}
  }}
}}
"""

SHOP_PRODUCTS_QUERY = f"""
query ShopProducts($first: Int!, $sortKey: ProductSortKeys, $reverse: Boolean) {{
  products(first: $first, sortKey: $sortKey, reverse: $reverse) {{
    nodes {{
      {PRODUCT_FIELDS}
    }}
  }}
}}
"""

PRODUCT_BY_HANDLE_QUERY = f"""
query ProductByHandle($handle: String!) {{
  product(handle: $handle) {{
    {PRODUCT_FIELDS}
  }}
}}
"""

SEARCH_PRODUCTS_QUERY = f"""
query SearchProducts($query: String!, $first: Int!) {{
  products(first: $first, query: $query) {{
    nodes {{
      {PRODUCT_FIELDS}
    }}
  }}
}}
"""

CART_FIELDS = """
  id
  checkoutUrl
  totalQuantity
  cost {
    subtotalAmount { amount currencyCode }
    totalAmount { amount currencyCode }
    totalTaxAmount { amount currencyCode }
  }
  lines(first: 100) {
    nodes {
      id
      quantity
      cost {
        totalAmount { amount currencyCode }
      }
      merchandise {
        ... on ProductVariant {
          id
          title
          availableForSale
          quantityAvailable
          image { url altText }
          price { amount currencyCode }
          product {
            id
            handle
            title
          }
          selectedOptions { name value }
        }
      }
    }
  }
"""

CART_BUYER_IDENTITY_UPDATE_MUTATION = f"""
mutation CartBuyerIdentityUpdate(
  $cartId: ID!
  $customerAccessToken: String!
  $deliveryAddressPreferences: [DeliveryAddressInput!]
) {{
  cartBuyerIdentityUpdate(
    cartId: $cartId
    buyerIdentity: {{
      customerAccessToken: $customerAccessToken
      deliveryAddressPreferences: $deliveryAddressPreferences
    }}
  ) {{
    cart {{
      {CART_FIELDS}
    }}
    userErrors {{ field message code }}
  }}
}}
"""

CART_CREATE_MUTATION = f"""
mutation CartCreate($input: CartInput) {{
  cartCreate(input: $input) {{
    cart {{
      {CART_FIELDS}
    }}
    userErrors {{ field message code }}
  }}
}}
"""

CART_GET_QUERY = f"""
query CartGet($cartId: ID!) {{
  cart(id: $cartId) {{
    {CART_FIELDS}
  }}
}}
"""

CART_LINES_ADD_MUTATION = f"""
mutation CartLinesAdd($cartId: ID!, $lines: [CartLineInput!]!) {{
  cartLinesAdd(cartId: $cartId, lines: $lines) {{
    cart {{
      {CART_FIELDS}
    }}
    userErrors {{ field message code }}
  }}
}}
"""

CART_LINES_UPDATE_MUTATION = f"""
mutation CartLinesUpdate($cartId: ID!, $lines: [CartLineUpdateInput!]!) {{
  cartLinesUpdate(cartId: $cartId, lines: $lines) {{
    cart {{
      {CART_FIELDS}
    }}
    userErrors {{ field message code }}
  }}
}}
"""

CART_LINES_REMOVE_MUTATION = f"""
mutation CartLinesRemove($cartId: ID!, $lineIds: [ID!]!) {{
  cartLinesRemove(cartId: $cartId, lineIds: $lineIds) {{
    cart {{
      {CART_FIELDS}
    }}
    userErrors {{ field message code }}
  }}
}}
"""

CART_ATTRIBUTES_UPDATE_MUTATION = """
mutation CartAttributesUpdate($cartId: ID!, $attributes: [AttributeInput!]!) {
  cartAttributesUpdate(cartId: $cartId, attributes: $attributes) {
    cart { id }
    userErrors { field message code }
  }
}
"""
