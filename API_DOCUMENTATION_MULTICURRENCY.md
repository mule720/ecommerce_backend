# Multi-Currency API Documentation

## Overview

The Multi-Currency API provides endpoints for managing currencies, exchange rates, pricing conversions, and tax calculations. All prices are handled as Decimal types to ensure accuracy.

## Base URL

```
/api/v1/
```

## Authentication

All endpoints require authentication unless otherwise noted. Use JWT token in header:

```
Authorization: Bearer {token}
```

## Currency Endpoints

### 1. Get All Currencies

**Endpoint:** `GET /currencies/`

**Description:** Retrieve list of all active currencies

**Response:**
```json
[
  {
    "code": "USD",
    "name": "United States Dollar",
    "symbol": "$",
    "country": "United States",
    "is_default": true,
    "decimal_places": 2,
    "symbol_position": "before"
  },
  {
    "code": "EUR",
    "name": "Euro",
    "symbol": "€",
    "country": "European Union",
    "is_default": false,
    "decimal_places": 2,
    "symbol_position": "after"
  }
]
```

### 2. Get Specific Currency

**Endpoint:** `GET /currencies/{code}/`

**Parameters:**
- `code` (string): ISO 4217 currency code (e.g., "USD")

**Response:**
```json
{
  "code": "USD",
  "name": "United States Dollar",
  "symbol": "$",
  "country": "United States",
  "is_default": true,
  "decimal_places": 2,
  "symbol_position": "before",
  "thousands_separator": ",",
  "decimal_separator": "."
}
```

## Exchange Rate Endpoints

### 1. Get Exchange Rate

**Endpoint:** `GET /exchange-rates/`

**Parameters:**
- `from_currency` (string, required): Source currency code
- `to_currency` (string, required): Target currency code
- `date` (string, optional): Date in YYYY-MM-DD format (defaults to today)

**Query Example:**
```
GET /exchange-rates/?from_currency=USD&to_currency=EUR&date=2024-01-15
```

**Response:**
```json
{
  "from_currency": "USD",
  "to_currency": "EUR",
  "rate": "0.92000000",
  "rate_date": "2024-01-15",
  "source": "openexchangerates"
}
```

### 2. Convert Currency

**Endpoint:** `POST /exchange-rates/convert/`

**Request Body:**
```json
{
  "amount": "100.00",
  "from_currency": "USD",
  "to_currency": "EUR",
  "date": "2024-01-15"
}
```

**Response:**
```json
{
  "from_currency": "USD",
  "to_currency": "EUR",
  "original_amount": "100.00",
  "converted_amount": "92.00",
  "exchange_rate": "0.92000000",
  "rate_date": "2024-01-15",
  "formatted_converted": "€92.00"
}
```

### 3. Create Exchange Rate

**Endpoint:** `POST /exchange-rates/`

**Permissions:** Admin only

**Request Body:**
```json
{
  "from_currency": "USD",
  "to_currency": "EUR",
  "rate": "0.92",
  "rate_date": "2024-01-15",
  "source": "manual"
}
```

**Response:**
```json
{
  "id": 1,
  "from_currency": "USD",
  "to_currency": "EUR",
  "rate": "0.92000000",
  "rate_date": "2024-01-15",
  "source": "manual"
}
```

### 4. Update Exchange Rates from API

**Endpoint:** `POST /exchange-rates/update-from-api/`

**Permissions:** Admin only

**Parameters:**
- `provider` (string, optional): API provider ("openexchangerates" or "fixer")

**Request Body:**
```json
{
  "provider": "openexchangerates"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Exchange rates updated successfully",
  "updated_count": 45,
  "timestamp": "2024-01-15T10:30:00Z"
}
```

## Product Pricing Endpoints

### 1. Get Product Price in Currency

**Endpoint:** `GET /products/{id}/price/`

**Parameters:**
- `currency` (string, optional): Target currency code (defaults to USD)

**Query Example:**
```
GET /products/123/price/?currency=EUR
```

**Response:**
```json
{
  "product_id": 123,
  "price": "92.00",
  "compare_at_price": "120.00",
  "cost": "45.00",
  "currency": "EUR",
  "discount_percentage": "23.33",
  "is_custom_price": false,
  "formatted_price": "€92.00"
}
```

### 2. Get Available Currencies for Product

**Endpoint:** `GET /products/{id}/currencies/`

**Response:**
```json
{
  "product_id": 123,
  "available_currencies": ["USD", "EUR", "GBP", "JPY"]
}
```

### 3. Create Product Pricing

**Endpoint:** `POST /product-pricing/`

**Permissions:** Vendor or Admin

**Request Body:**
```json
{
  "product": 123,
  "currency": "EUR",
  "price": "92.00",
  "compare_at_price": "120.00",
  "cost": "45.00",
  "is_custom_price": false
}
```

**Response:**
```json
{
  "id": 45,
  "product": 123,
  "currency": "EUR",
  "price": "92.00",
  "compare_at_price": "120.00",
  "cost": "45.00",
  "discount_percentage": "23.33",
  "is_custom_price": false,
  "is_base_currency": false
}
```

### 4. Update Product Pricing

**Endpoint:** `PATCH /product-pricing/{id}/`

**Permissions:** Vendor (owner) or Admin

**Request Body:**
```json
{
  "price": "94.00",
  "compare_at_price": "125.00"
}
```

### 5. Delete Product Pricing

**Endpoint:** `DELETE /product-pricing/{id}/`

**Permissions:** Vendor (owner) or Admin

**Response:**
```json
{
  "success": true,
  "message": "Product pricing deleted"
}
```

## Tax Endpoints

### 1. Get Tax Rate

**Endpoint:** `GET /tax-rates/`

**Parameters:**
- `country_code` (string, required): 2-letter country code
- `state_province` (string, optional): State or province name
- `currency` (string, optional): Currency code (defaults to USD)

**Query Example:**
```
GET /tax-rates/?country_code=US&state_province=CA&currency=USD
```

**Response:**
```json
{
  "country_code": "US",
  "state_province": "CA",
  "tax_type": "sales_tax",
  "tax_rate": "8.25",
  "currency": "USD"
}
```

### 2. Calculate Tax

**Endpoint:** `POST /tax-rates/calculate/`

**Request Body:**
```json
{
  "subtotal": "100.00",
  "country_code": "US",
  "state_province": "CA",
  "currency": "USD",
  "include_shipping": false,
  "shipping_amount": "0.00"
}
```

**Response:**
```json
{
  "subtotal": "100.00",
  "tax_amount": "8.25",
  "total": "108.25",
  "tax_rate": "8.25",
  "currency": "USD"
}
```

### 3. List All Tax Rates

**Endpoint:** `GET /tax-rates/list/`

**Parameters:**
- `country_code` (string, optional): Filter by country
- `currency` (string, optional): Filter by currency

**Response:**
```json
[
  {
    "id": 1,
    "country_code": "US",
    "state_province": "CA",
    "tax_type": "sales_tax",
    "tax_rate": "8.25",
    "currency": "USD"
  },
  {
    "id": 2,
    "country_code": "UK",
    "state_province": "",
    "tax_type": "vat",
    "tax_rate": "20.00",
    "currency": "GBP"
  }
]
```

### 4. Create Tax Rate

**Endpoint:** `POST /tax-rates/`

**Permissions:** Admin only

**Request Body:**
```json
{
  "country_code": "DE",
  "state_province": "",
  "tax_type": "vat",
  "tax_rate": "19.00",
  "currency": "EUR"
}
```

## Order Endpoints (Multi-Currency)

### 1. Create Order with Currency

**Endpoint:** `POST /orders/`

**Request Body:**
```json
{
  "customer": 1,
  "currency": "EUR",
  "items": [
    {
      "product": 123,
      "quantity": 2
    }
  ],
  "shipping_country": "DE",
  "shipping_state": ""
}
```

**Response:**
```json
{
  "id": 1,
  "order_number": "ORD-2024-00001",
  "customer": 1,
  "currency": "EUR",
  "base_currency": "USD",
  "exchange_rate": "0.92",
  "subtotal": "100.00",
  "tax_amount": "19.00",
  "shipping_amount": "9.20",
  "discount_amount": "0.00",
  "total": "128.20",
  "status": "pending"
}
```

### 2. Set Order Currency

**Endpoint:** `PATCH /orders/{id}/set-currency/`

**Request Body:**
```json
{
  "currency": "GBP"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Order currency changed to GBP",
  "order": {
    "id": 1,
    "currency": "GBP",
    "exchange_rate": "0.79",
    "subtotal": "79.00",
    "tax_amount": "...",
    "total": "..."
  }
}
```

### 3. Calculate Order Tax

**Endpoint:** `POST /orders/{id}/calculate-tax/`

**Response:**
```json
{
  "success": true,
  "message": "Tax calculated and applied",
  "tax_amount": "19.00",
  "total": "128.20"
}
```

### 4. Get Order Summary

**Endpoint:** `GET /orders/{id}/summary/`

**Response:**
```json
{
  "order_number": "ORD-2024-00001",
  "currency": "EUR",
  "subtotal": "100.00",
  "tax_amount": "19.00",
  "shipping_amount": "9.20",
  "discount_amount": "0.00",
  "total": "128.20",
  "exchange_rate": "0.92",
  "exchange_rate_date": "2024-01-15"
}
```

## Cart Endpoints (Multi-Currency)

### 1. Create Cart

**Endpoint:** `POST /carts/`

**Request Body:**
```json
{
  "customer": 1,
  "currency": "EUR"
}
```

**Response:**
```json
{
  "id": 1,
  "customer": 1,
  "currency": "EUR",
  "total": "0.00",
  "item_count": 0
}
```

### 2. Get Cart

**Endpoint:** `GET /carts/{id}/`

**Response:**
```json
{
  "id": 1,
  "customer": 1,
  "currency": "EUR",
  "items": [
    {
      "id": 1,
      "product": 123,
      "quantity": 2,
      "unit_price": "46.00",
      "total_price": "92.00"
    }
  ],
  "total": "92.00",
  "item_count": 1
}
```

### 3. Set Cart Currency

**Endpoint:** `PATCH /carts/{id}/set-currency/`

**Request Body:**
```json
{
  "currency": "GBP"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Cart currency changed to GBP",
  "currency": "GBP",
  "total": "79.00"
}
```

### 4. Add Item to Cart

**Endpoint:** `POST /carts/{id}/items/`

**Request Body:**
```json
{
  "product": 123,
  "quantity": 2
}
```

**Response:**
```json
{
  "id": 1,
  "cart": 1,
  "product": 123,
  "quantity": 2,
  "unit_price": "46.00",
  "total_price": "92.00"
}
```

## Error Responses

### 400 Bad Request

```json
{
  "error": "Invalid currency code",
  "code": "INVALID_CURRENCY",
  "details": "Currency 'XYZ' is not supported"
}
```

### 404 Not Found

```json
{
  "error": "Resource not found",
  "code": "NOT_FOUND",
  "details": "Currency 'ZZZ' does not exist"
}
```

### 403 Forbidden

```json
{
  "error": "Permission denied",
  "code": "FORBIDDEN",
  "details": "You don't have permission to perform this action"
}
```

### 429 Too Many Requests

```json
{
  "error": "Rate limit exceeded",
  "code": "RATE_LIMIT",
  "details": "Maximum 1000 requests per hour exceeded",
  "retry_after": 3600
}
```

### 500 Internal Server Error

```json
{
  "error": "Internal server error",
  "code": "SERVER_ERROR",
  "details": "An unexpected error occurred"
}
```

## GraphQL Queries

### Get Product Price in Currency

```graphql
query {
  productPriceInCurrency(productId: 123, currency: "EUR") {
    price
    compareAtPrice
    currency
    discountPercentage
    formattedPrice
  }
}
```

### Convert Currency

```graphql
query {
  convertCurrency(
    amount: 100.00
    fromCurrency: "USD"
    toCurrency: "EUR"
  ) {
    originalAmount
    convertedAmount
    exchangeRate
    formattedConverted
  }
}
```

### Get Tax Rate

```graphql
query {
  taxRate(
    countryCode: "US"
    stateProvince: "CA"
    currency: "USD"
  ) {
    countryCode
    stateProvince
    taxType
    taxRate
    currency
  }
}
```

## Webhooks

### Currency Changed

**Event:** `currency.changed`

```json
{
  "event": "currency.changed",
  "timestamp": "2024-01-15T10:30:00Z",
  "data": {
    "currency_code": "USD",
    "is_active": true,
    "changed_fields": ["symbol_position", "thousands_separator"]
  }
}
```

### Exchange Rate Updated

**Event:** `exchange_rate.updated`

```json
{
  "event": "exchange_rate.updated",
  "timestamp": "2024-01-15T10:30:00Z",
  "data": {
    "from_currency": "USD",
    "to_currency": "EUR",
    "new_rate": "0.92",
    "old_rate": "0.91",
    "rate_date": "2024-01-15",
    "source": "openexchangerates"
  }
}
```

## Rate Limiting

- Standard rate limit: 1000 requests per hour
- Authenticated users: 5000 requests per hour
- Admin users: Unlimited

## Pagination

List endpoints support pagination:

```
GET /currencies/?page=1&page_size=20
GET /exchange-rates/?page=2&page_size=50
```

Response includes:

```json
{
  "count": 100,
  "next": "http://api.example.com/currencies/?page=2",
  "previous": null,
  "results": [...]
}
```

## Filtering

Filter endpoints by various criteria:

```
GET /tax-rates/?country_code=US&currency=USD
GET /product-pricing/?product=123&is_custom_price=true
GET /order-items/?currency=EUR&created_after=2024-01-01
```

## Sorting

Sort endpoints using `ordering` parameter:

```
GET /exchange-rates/?ordering=-rate_date
GET /currencies/?ordering=name
GET /product-pricing/?ordering=price
```

## Bulk Operations

### Bulk Update Exchange Rates

```json
POST /exchange-rates/bulk-create/
{
  "rates": [
    {"from_currency": "USD", "to_currency": "EUR", "rate": "0.92", "rate_date": "2024-01-15"},
    {"from_currency": "USD", "to_currency": "GBP", "rate": "0.79", "rate_date": "2024-01-15"}
  ]
}
```

## Version History

- **v1.0** (2024-01-15): Initial release
  - Currency management
  - Exchange rates
  - Product pricing
  - Orders with currency support
  - Tax calculations
