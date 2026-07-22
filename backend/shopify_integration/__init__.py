"""
Now Kart — Shopify Storefront API integration package.

Layers:
  config.py    -> environment-driven settings
  client.py    -> low-level GraphQL transport (auth headers, error handling)
  queries.py   -> raw GraphQL query/mutation strings
  mappers.py   -> raw Shopify JSON -> our domain-shaped dicts
  schemas.py   -> Pydantic response models returned by our own API
  cache.py     -> lightweight in-memory TTL cache
  service.py   -> business logic orchestrating client+queries+mappers+cache
  collection_groups.py -> static UI grouping config (which collection handles
                           belong under which Home-screen section heading)
  router.py    -> FastAPI routes exposed to the Expo frontend under /api
"""
