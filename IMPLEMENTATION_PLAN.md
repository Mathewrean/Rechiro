# FishNet E-commerce Implementation Plan

## Overview
Transform Sustainable_Fishing into FishNet - a full fish e-commerce marketplace with Fishermen and Customers roles.

## Phase 1: Models & Database (Day 1)
### 1.1 Update User Model
- [ ] Remove 'educator' role from User.ROLE_CHOICES
- [ ] Add 'customer' role
- [ ] Keep only fisherman and customer roles

### 1.2 Create Profile Models
- [ ] FishermanProfile: phone, location, contact_details, verified_status
- [ ] CustomerProfile: phone, delivery_location, fulfillment_method (pickup/delivery)

### 1.3 Create E-commerce Models
- [ ] Fish: fisherman, name, fish_type, description, price_per_kg, available_weight, image, is_active, created_at
- [ ] Cart: user, created_at, updated_at
- [ ] CartItem: cart, fish, weight_kg (default 1), added_at
- [ ] Order: user, order_number, status (PENDING/PAID/FAILED/CANCELLED/DELIVERED), total_amount, created_at, updated_at
- [ ] OrderItem: order, fish, fisherman, weight_kg, price_per_kg, total_price
- [ ] PaymentTransaction: order, transaction_id, amount, status, mpesa_receipt_number, created_at
- [ ] Delivery: order, status, estimated_delivery, actual_delivery, delivery_notes

## Phase 2: M-Pesa Integration (Day 2)
### 2.1 Create M-Pesa Service
- [ ] OAuth token generation with Consumer Key/Secret
- [ ] Token storage and refresh mechanism
- [ ] STK Push initiation
- [ ] Callback handling (C2B)
- [ ] Transaction verification

### 2.2 Environment Configuration
- [ ] Add M-Pesa credentials to settings
- [ ] Create secure credential storage

## Phase 3: Views & URLs (Day 3)
### 3.1 Marketplace Views
- [ ] fish_marketplace: Amazon-style grid display
- [ ] fish_detail: product page with weight selection
- [ ] add_to_cart
- [ ] cart_view
- [ ] update_cart_item
- [ ] remove_from_cart
- [ ] checkout_initiate
- [ ] checkout_process
- [ ] order_confirm
- [ ] order_list
- [ ] order_detail
- [ ] delivery_tracking

### 3.2 Fisherman Dashboard
- [ ] my_fish_listing
- [ ] add_fish
- [ ] edit_fish
- [ ] delete_fish
- [ ] order_fulfillment
- [ ] sales_history

### 3.3 Customer Dashboard
- [ ] order_history
- [ ] payment_status
- [ ] delivery_updates

### 3.4 URL Configuration
- [ ] fishing: marketplace URLs
- [ ] users: customer/fisherman specific URLs
- [ ] api: payment callbacks

## Phase 4: Templates (Day 4)
### 4.1 Base & Navigation
- [ ] Update base.html with marketplace nav
- [ ] Add cart icon with count
- [ ] Role-based menu items

### 4.2 Marketplace Templates
- [ ] marketplace.html: Fish grid with filters
- [ ] fish_detail.html: Product page
- [ ] cart.html: Shopping cart
- [ ] checkout.html: Payment initiation

### 4.3 Order Templates
- [ ] order_list.html
- [ ] order_detail.html
- [ ] order_confirm.html

### 4.4 Dashboard Templates
- [ ] fisherman_dashboard.html
- [ ] customer_dashboard.html
- [ ] fulfillment_manager.html

### 4.5 Delivery Templates
- [ ] delivery_tracking.html
- [ ] delivery_confirm.html

## Phase 5: Forms & Admin (Day 5)
### 5.1 Forms
- [ ] FishForm
- [ ] CartItemForm
- [ ] CustomerProfileForm
- [ ] FishermanProfileForm
- [ ] DeliveryUpdateForm

### 5.2 Admin Configuration
- [ ] Register all models
- [ ] Customize admin interfaces
- [ ] Add search and filters

## Phase 6: Cleanup & Testing (Day 6)
### 6.1 Remove Old Modules
- [ ] Remove content app entirely
- [ ] Remove catch-related code
- [ ] Remove educator references

### 6.2 Update Settings
- [ ] Remove content from INSTALLED_APPS
- [ ] Add marketplace context processors
- [ ] Configure M-Pesa settings

### 6.3 Testing
- [ ] Test user registration (both roles)
- [ ] Test fish listing workflow
- [ ] Test cart functionality
- [ ] Test order flow
- [ ] Verify stock management

## Phase 7: Documentation & Deployment (Day 7)
### 7.1 Documentation
- [ ] Update README.md
- [ ] Add M-Pesa setup guide
- [ ] Create API documentation

### 7.2 Deployment Prep
- [ ] Environment variable checklist
- [ ] Database migrations
- [ ] Static file collection
- [ ] Production settings

## Implementation Order (Priority)
1. Update User model and create profiles
2. Create Fish, Cart, Order models
3. Create M-Pesa service
4. Create marketplace views and URLs
5. Create templates
6. Remove old content
7. Test and polish

## Dependencies
- django-crispy-forms (for better forms)
- python-mpesa SDK or custom implementation
- django-countries (optional, for location fields)

## Estimated Timeline
- Days 1-2: Core models and M-Pesa integration
- Days 3-4: Views, URLs, and templates
- Days 5-6: Forms, admin, and cleanup
- Day 7: Testing and documentation

## Success Criteria
- [ ] Fishermen can list fish for sale
- [ ] Customers can browse and purchase fish
- [ ] Weight-based pricing works correctly
- [ ] M-Pesa payments process successfully
- [ ] Stock is managed properly
- [ ] Delivery status updates work
- [ ] Clean, intuitive UI

