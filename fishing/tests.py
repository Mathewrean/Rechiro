import json
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from users.models import User, FishermanProfile, CustomerProfile
from .models import (
    Fish,
    Cart,
    CartItem,
    Order,
    PaymentTransaction,
    Delivery,
    PickupPoint,
    DeliveryAuditLog,
)


class CheckoutAndPaymentFlowTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            username='buyer',
            password='testpass123',
            role='customer',
            phone='0712345678',
            email='buyer@example.com',
        )
        CustomerProfile.objects.create(
            user=self.customer,
            phone='0712345678',
            delivery_location='Nairobi',
            delivery_address='Test Address',
            preferred_fulfillment='delivery',
        )
        self.fisherman = User.objects.create_user(
            username='fisher',
            password='testpass123',
            role='fisherman',
            phone='0700000000',
            email='fisher@example.com',
        )
        FishermanProfile.objects.create(
            user=self.fisherman,
            phone='0700000000',
            location='Lake side',
            contact_details='Dock 1',
            is_verified=True,
            mpesa_phone='0700000000',
            mpesa_payment_type='PAYBILL',
            mpesa_paybill_number='400200',
            mpesa_account_reference='FISHER001',
        )
        self.fish = Fish.objects.create(
            fisherman=self.fisherman,
            name='Tilapia Fresh',
            fish_type='tilapia',
            price_per_kg=Decimal('500.00'),
            available_weight=Decimal('10.00'),
            catch_date='2026-02-10',
            status='available',
        )

    @patch('fishing.views.initiate_stk_push')
    def test_checkout_creates_pending_transaction_per_item(self, mock_stk):
        mock_stk.return_value = {
            'success': True,
            'merchant_request_id': 'MRQ1',
            'checkout_request_id': 'CRQ1',
        }

        self.client.login(username='buyer', password='testpass123')
        cart = Cart.objects.create(user=self.customer)
        CartItem.objects.create(cart=cart, fish=self.fish, weight_kg=Decimal('2.00'))

        response = self.client.post(reverse('fishing:checkout_process'), {
            'fulfillment_method': 'delivery',
            'delivery_location': 'Nairobi CBD',
            'delivery_address': 'Moi Avenue',
            'delivery_notes': 'Call on arrival',
        })
        self.assertEqual(response.status_code, 302)

        order = Order.objects.get(customer=self.customer)
        self.assertEqual(order.status, 'PENDING')
        self.assertEqual(order.total_amount, Decimal('1000.00'))
        self.assertEqual(order.platform_fee, Decimal('20.00'))
        self.assertEqual(order.fishermen_net_amount, Decimal('980.00'))

        tx = PaymentTransaction.objects.get(order=order)
        self.assertEqual(tx.status, 'PENDING')
        self.assertEqual(tx.amount, Decimal('1000.00'))
        self.assertEqual(tx.platform_fee, Decimal('20.00'))
        self.assertEqual(tx.net_payout, Decimal('980.00'))

    @patch('fishing.views.initiate_stk_push')
    def test_checkout_allows_unverified_fisherman_when_mpesa_config_is_complete(self, mock_stk):
        profile = self.fisherman.fisherman_profile
        profile.is_verified = False
        profile.save(update_fields=['is_verified'])
        mock_stk.return_value = {
            'success': True,
            'merchant_request_id': 'MRQ9',
            'checkout_request_id': 'CRQ9',
        }

        self.client.login(username='buyer', password='testpass123')
        cart = Cart.objects.create(user=self.customer)
        CartItem.objects.create(cart=cart, fish=self.fish, weight_kg=Decimal('1.00'))
        response = self.client.post(reverse('fishing:checkout_process'), {
            'fulfillment_method': 'delivery',
            'delivery_location': 'Nairobi CBD',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Order.objects.filter(customer=self.customer).exists())
        profile.refresh_from_db()
        self.assertTrue(profile.is_verified)

    @patch('fishing.views.initiate_stk_push')
    def test_callback_success_marks_fully_paid_and_delivery_in_progress(self, mock_stk):
        mock_stk.return_value = {
            'success': True,
            'merchant_request_id': 'MRQ2',
            'checkout_request_id': 'CRQ2',
        }

        self.client.login(username='buyer', password='testpass123')
        cart = Cart.objects.create(user=self.customer)
        CartItem.objects.create(cart=cart, fish=self.fish, weight_kg=Decimal('1.00'))
        self.client.post(reverse('fishing:checkout_process'), {
            'fulfillment_method': 'delivery',
            'delivery_location': 'Nairobi CBD',
        })

        callback_payload = {
            'Body': {
                'stkCallback': {
                    'MerchantRequestID': 'MRQ2',
                    'CheckoutRequestID': 'CRQ2',
                    'ResultCode': 0,
                    'ResultDesc': 'The service request is processed successfully.',
                    'CallbackMetadata': {
                        'Item': [
                            {'Name': 'Amount', 'Value': 500},
                            {'Name': 'MpesaReceiptNumber', 'Value': 'NLJ7RT61SV'},
                            {'Name': 'TransactionDate', 'Value': 20260211120000},
                            {'Name': 'PhoneNumber', 'Value': 254712345678},
                        ]
                    }
                }
            }
        }
        response = self.client.post(
            reverse('fishing:mpesa_callback'),
            data=json.dumps(callback_payload),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)

        order = Order.objects.get(customer=self.customer)
        self.assertEqual(order.status, 'DELIVERY_IN_PROGRESS')
        tx = PaymentTransaction.objects.get(order=order)
        self.assertEqual(tx.status, 'COMPLETED')
        self.assertTrue(Delivery.objects.filter(order=order, status='DELIVERY_IN_PROGRESS').exists())

    @patch('fishing.views.initiate_stk_push')
    def test_callback_amount_mismatch_rejected(self, mock_stk):
        mock_stk.return_value = {
            'success': True,
            'merchant_request_id': 'MRQ3',
            'checkout_request_id': 'CRQ3',
        }

        self.client.login(username='buyer', password='testpass123')
        cart = Cart.objects.create(user=self.customer)
        CartItem.objects.create(cart=cart, fish=self.fish, weight_kg=Decimal('1.00'))
        self.client.post(reverse('fishing:checkout_process'), {
            'fulfillment_method': 'delivery',
            'delivery_location': 'Nairobi CBD',
        })

        bad_amount_payload = {
            'Body': {
                'stkCallback': {
                    'MerchantRequestID': 'MRQ3',
                    'CheckoutRequestID': 'CRQ3',
                    'ResultCode': 0,
                    'ResultDesc': 'The service request is processed successfully.',
                    'CallbackMetadata': {
                        'Item': [
                            {'Name': 'Amount', 'Value': 200},
                            {'Name': 'MpesaReceiptNumber', 'Value': 'NLJ7RT61SX'},
                        ]
                    }
                }
            }
        }
        response = self.client.post(
            reverse('fishing:mpesa_callback'),
            data=json.dumps(bad_amount_payload),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)


class DeliveryAndPickupEndpointsTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            username='customer1', password='testpass123', role='customer', phone='0711111111', email='c1@example.com'
        )
        self.delivery_user = User.objects.create_user(
            username='deliver1', password='testpass123', role='delivery', phone='0722222222', email='d1@example.com'
        )
        self.order = Order.objects.create(
            customer=self.customer,
            status='READY_FOR_PICKUP',
            total_amount=Decimal('1000.00'),
            platform_fee=Decimal('20.00'),
            fishermen_net_amount=Decimal('980.00'),
            fulfillment_method='pickup',
            customer_phone='0711111111',
            customer_email='c1@example.com',
        )
        self.delivery = Delivery.objects.create(order=self.order, status='READY_FOR_PICKUP')
        PickupPoint.objects.create(
            name='Westlands Hub',
            general_location='Westlands',
            contact_person='Alice',
            phone_number='0700000001',
            latitude=Decimal('-1.2670000'),
            longitude=Decimal('36.8100000'),
        )

    def test_pickup_points_requires_auth(self):
        response = self.client.get(reverse('fishing:pickup_points_api'))
        self.assertEqual(response.status_code, 302)

    def test_pickup_points_returns_data(self):
        self.client.login(username='customer1', password='testpass123')
        response = self.client.get(reverse('fishing:pickup_points_api'), {'lat': '-1.26', 'lng': '36.81'})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn('pickup_points', payload)
        self.assertEqual(len(payload['pickup_points']), 1)

    def test_delivery_status_update_secured_and_audited(self):
        self.client.login(username='customer1', password='testpass123')
        forbidden = self.client.post(reverse('fishing:delivery_status_update', args=[self.order.order_number]), {'status': 'DELIVERED'})
        self.assertEqual(forbidden.status_code, 403)

        self.client.login(username='deliver1', password='testpass123')
        ok = self.client.post(reverse('fishing:delivery_status_update', args=[self.order.order_number]), {'status': 'DELIVERED'})
        self.assertEqual(ok.status_code, 200)

        self.order.refresh_from_db()
        self.delivery.refresh_from_db()
        self.assertEqual(self.order.status, 'DELIVERED')
        self.assertEqual(self.delivery.status, 'DELIVERED')
        self.assertTrue(DeliveryAuditLog.objects.filter(order=self.order, new_status='DELIVERED').exists())

    def test_manage_pickup_points_page_allows_delivery_role_to_add(self):
        self.client.login(username='deliver1', password='testpass123')
        response = self.client.post(reverse('fishing:manage_pickup_points'), {
            'name': 'Kilimani Point',
            'general_location': 'Kilimani',
            'contact_person': 'Bob',
            'phone_number': '0700000002',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(PickupPoint.objects.filter(name='Kilimani Point').exists())
