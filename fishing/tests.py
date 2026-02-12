import json
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile

from users.models import User, FishermanProfile, CustomerProfile, BeachChairmanProfile
from users.models import PhoneVerificationTransaction
from .models import (
    Fish,
    Cart,
    CartItem,
    Order,
    PaymentTransaction,
    Delivery,
    PickupPoint,
    DeliveryAuditLog,
    SellerNotification,
    ChairmanApprovalRequest,
)


class CheckoutAndPaymentFlowTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            username='buyer',
            password='testpass123',
            role='customer',
            phone='0712345678',
            email='buyer@example.com',
            email_verified=True,
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
            phone_verified=True,
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
    def test_checkout_uses_paybill_transaction_type_for_stk_push(self, mock_stk):
        profile = self.fisherman.fisherman_profile
        profile.mpesa_payment_type = 'STK_PUSH'
        profile.mpesa_paybill_number = ''
        profile.mpesa_till_number = ''
        profile.save(update_fields=['mpesa_payment_type', 'mpesa_paybill_number', 'mpesa_till_number'])
        mock_stk.return_value = {
            'success': True,
            'merchant_request_id': 'MRQ10',
            'checkout_request_id': 'CRQ10',
        }

        self.client.login(username='buyer', password='testpass123')
        cart = Cart.objects.create(user=self.customer)
        CartItem.objects.create(cart=cart, fish=self.fish, weight_kg=Decimal('1.00'))
        self.client.post(reverse('fishing:checkout_process'), {
            'fulfillment_method': 'delivery',
            'delivery_location': 'Nairobi CBD',
        })

        self.assertTrue(mock_stk.called)
        _, kwargs = mock_stk.call_args
        self.assertEqual(kwargs['transaction_type'], 'CustomerPayBillOnline')

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
        self.assertEqual(tx.mpesa_receipt_number, 'NLJ7RT61SV')
        self.assertTrue(Delivery.objects.filter(order=order, status='DELIVERY_IN_PROGRESS').exists())
        self.assertTrue(SellerNotification.objects.filter(payment_transaction=tx).exists())

    @patch('fishing.views.initiate_stk_push')
    def test_duplicate_callback_is_idempotent(self, mock_stk):
        mock_stk.return_value = {
            'success': True,
            'merchant_request_id': 'MRQ4',
            'checkout_request_id': 'CRQ4',
        }

        self.client.login(username='buyer', password='testpass123')
        cart = Cart.objects.create(user=self.customer)
        CartItem.objects.create(cart=cart, fish=self.fish, weight_kg=Decimal('1.00'))
        self.client.post(reverse('fishing:checkout_process'), {
            'fulfillment_method': 'delivery',
            'delivery_location': 'Nairobi CBD',
        })

        payload = {
            'Body': {
                'stkCallback': {
                    'MerchantRequestID': 'MRQ4',
                    'CheckoutRequestID': 'CRQ4',
                    'ResultCode': 0,
                    'ResultDesc': 'Success',
                    'CallbackMetadata': {
                        'Item': [
                            {'Name': 'Amount', 'Value': 500},
                            {'Name': 'MpesaReceiptNumber', 'Value': 'RLJ7RT61SV'},
                        ]
                    }
                }
            }
        }
        first = self.client.post(reverse('fishing:mpesa_callback'), data=json.dumps(payload), content_type='application/json')
        second = self.client.post(reverse('fishing:mpesa_callback'), data=json.dumps(payload), content_type='application/json')
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)

        tx = PaymentTransaction.objects.get(checkout_request_id='CRQ4')
        self.assertEqual(tx.status, 'COMPLETED')
        self.assertEqual(SellerNotification.objects.filter(payment_transaction=tx).count(), 1)

    @patch('fishing.views.initiate_stk_push')
    def test_api_callback_alias_endpoint_works(self, mock_stk):
        mock_stk.return_value = {
            'success': True,
            'merchant_request_id': 'MRQ5',
            'checkout_request_id': 'CRQ5',
        }
        self.client.login(username='buyer', password='testpass123')
        cart = Cart.objects.create(user=self.customer)
        CartItem.objects.create(cart=cart, fish=self.fish, weight_kg=Decimal('1.00'))
        self.client.post(reverse('fishing:checkout_process'), {
            'fulfillment_method': 'delivery',
            'delivery_location': 'Nairobi CBD',
        })
        payload = {
            'Body': {
                'stkCallback': {
                    'MerchantRequestID': 'MRQ5',
                    'CheckoutRequestID': 'CRQ5',
                    'ResultCode': 0,
                    'ResultDesc': 'Success',
                    'CallbackMetadata': {
                        'Item': [
                            {'Name': 'Amount', 'Value': 500},
                            {'Name': 'MpesaReceiptNumber', 'Value': 'ALIAS5'},
                        ]
                    }
                }
            }
        }
        response = self.client.post('/api/mpesa/callback/', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 200)

    @patch('fishing.views.initiate_stk_push')
    def test_fisherman_notification_api_returns_confirmed_payment_details(self, mock_stk):
        mock_stk.return_value = {
            'success': True,
            'merchant_request_id': 'MRQ6',
            'checkout_request_id': 'CRQ6',
        }
        self.client.login(username='buyer', password='testpass123')
        cart = Cart.objects.create(user=self.customer)
        CartItem.objects.create(cart=cart, fish=self.fish, weight_kg=Decimal('1.00'))
        self.client.post(reverse('fishing:checkout_process'), {
            'fulfillment_method': 'delivery',
            'delivery_location': 'Nairobi CBD',
        })
        payload = {
            'Body': {
                'stkCallback': {
                    'MerchantRequestID': 'MRQ6',
                    'CheckoutRequestID': 'CRQ6',
                    'ResultCode': 0,
                    'ResultDesc': 'Success',
                    'CallbackMetadata': {
                        'Item': [
                            {'Name': 'Amount', 'Value': 500},
                            {'Name': 'MpesaReceiptNumber', 'Value': 'NOTICE6'},
                        ]
                    }
                }
            }
        }
        self.client.post(reverse('fishing:mpesa_callback'), data=json.dumps(payload), content_type='application/json')

        self.client.login(username='fisher', password='testpass123')
        response = self.client.get(reverse('fishing:api_seller_notifications'))
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body.get('success'))
        self.assertGreaterEqual(body.get('unread_count', 0), 1)
        latest = body['notifications'][0]
        self.assertEqual(latest['receipt_number'], 'NOTICE6')

    def test_phone_verification_callback_marks_user_phone_verified(self):
        self.fisherman.phone_verified = False
        self.fisherman.save(update_fields=['phone_verified'])
        PhoneVerificationTransaction.objects.create(
            user=self.fisherman,
            phone_number='0700000000',
            amount=Decimal('1.00'),
            checkout_request_id='VERIFY-CRQ1',
            merchant_request_id='VERIFY-MRQ1',
            status='PENDING',
        )
        payload = {
            'Body': {
                'stkCallback': {
                    'MerchantRequestID': 'VERIFY-MRQ1',
                    'CheckoutRequestID': 'VERIFY-CRQ1',
                    'ResultCode': 0,
                    'ResultDesc': 'Success',
                    'CallbackMetadata': {
                        'Item': [
                            {'Name': 'Amount', 'Value': 1},
                            {'Name': 'MpesaReceiptNumber', 'Value': 'PV12345'},
                        ]
                    }
                }
            }
        }
        response = self.client.post(reverse('fishing:mpesa_callback'), data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.fisherman.refresh_from_db()
        self.assertTrue(self.fisherman.phone_verified)

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
            username='customer1', password='testpass123', role='customer', phone='0711111111', email='c1@example.com', email_verified=True
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


class FishImageUploadTests(TestCase):
    def setUp(self):
        self.fisherman = User.objects.create_user(
            username='imgfisher',
            password='testpass123',
            role='fisherman',
            phone='0700011111',
            email='imgfisher@example.com',
            phone_verified=True,
        )
        FishermanProfile.objects.create(
            user=self.fisherman,
            phone='0700011111',
            landing_site='Lake',
            location='Lake',
            contact_details='Dock',
            is_verified=True,
            chairman_approved=True,
            mpesa_phone='0700011111',
        )

    def _tiny_png(self, name='fish.png'):
        png_bytes = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDAT\x08\xd7c\xf8\x0f"
            b"\x00\x01\x01\x01\x00\x1a\x0b\x04]\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        return SimpleUploadedFile(name, png_bytes, content_type='image/png')

    def test_add_fish_accepts_image_upload(self):
        self.client.login(username='imgfisher', password='testpass123')
        response = self.client.post(
            reverse('fishing:add_fish'),
            {
                'name': 'Camera Omena',
                'fish_type': 'other',
                'description': 'Fresh',
                'price_per_kg': '400',
                'available_weight': '4',
                'catch_date': '2026-02-11',
                'location': 'Lake',
                'image': self._tiny_png(),
            },
        )
        self.assertEqual(response.status_code, 302)
        fish = Fish.objects.get(name='Camera Omena')
        self.assertTrue(bool(fish.image))

    def test_edit_fish_can_replace_image(self):
        fish = Fish.objects.create(
            fisherman=self.fisherman,
            name='Edit Omena',
            fish_type='other',
            price_per_kg=Decimal('300.00'),
            available_weight=Decimal('5.00'),
            catch_date='2026-02-11',
            image=self._tiny_png('old.png'),
        )
        old_name = fish.image.name
        self.client.login(username='imgfisher', password='testpass123')
        response = self.client.post(
            reverse('fishing:edit_fish', args=[fish.id]),
            {
                'name': fish.name,
                'fish_type': fish.fish_type,
                'description': fish.description,
                'price_per_kg': str(fish.price_per_kg),
                'available_weight': str(fish.available_weight),
                'catch_date': '2026-02-11',
                'location': fish.location,
                'preparation_notes': fish.preparation_notes,
                'image': self._tiny_png('new.png'),
            },
        )
        self.assertEqual(response.status_code, 302)
        fish.refresh_from_db()
        self.assertTrue(bool(fish.image))
        self.assertNotEqual(fish.image.name, old_name)


class ChairmanApprovalWorkflowTests(TestCase):
    def setUp(self):
        self.fisherman = User.objects.create_user(
            username='fisher2',
            password='testpass123',
            role='fisherman',
            phone='0700099999',
            email='f2@example.com',
            phone_verified=True,
        )
        self.profile = FishermanProfile.objects.create(
            user=self.fisherman,
            phone='0700099999',
            landing_site='Bondo',
            location='Bondo',
            contact_details='Pier',
            mpesa_phone='0700099999',
        )
        self.reviewer = User.objects.create_user(
            username='deliveryboss',
            password='testpass123',
            role='delivery',
            phone='0700088888',
            email='d2@example.com',
        )
        self.chairman = User.objects.create_user(
            username='beachchair',
            password='testpass123',
            role='chairman',
            phone='0700077777',
            email='chair@example.com',
        )
        BeachChairmanProfile.objects.create(
            user=self.chairman,
            beach_name='Bondo',
            phone='0700077777',
            notes='Lake chairman',
        )

    def test_fisherman_can_submit_approval_request(self):
        self.client.login(username='fisher2', password='testpass123')
        response = self.client.post(reverse('fishing:request_chairman_approval'), {'notes': 'Ready for review'})
        self.assertEqual(response.status_code, 302)
        request_obj = ChairmanApprovalRequest.objects.get(fisherman=self.fisherman)
        self.assertEqual(request_obj.status, 'PENDING')
        self.assertEqual(request_obj.notes, 'Ready for review')

    def test_delivery_role_can_approve_request(self):
        req = ChairmanApprovalRequest.objects.create(fisherman=self.fisherman, status='PENDING', notes='Please verify')
        self.client.login(username='deliveryboss', password='testpass123')
        response = self.client.post(
            reverse('fishing:review_chairman_approval', args=[req.id]),
            {'action': 'approve', 'notes': 'Approved by chairman'}
        )
        self.assertEqual(response.status_code, 302)
        req.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(req.status, 'APPROVED')
        self.assertEqual(req.reviewed_by, self.reviewer)
        self.assertTrue(self.profile.chairman_approved)

    def test_chairman_dashboard_filters_requests_by_beach(self):
        other_fisher = User.objects.create_user(
            username='otherfisher',
            password='testpass123',
            role='fisherman',
            phone='0700066666',
            email='other@example.com',
            phone_verified=True,
        )
        FishermanProfile.objects.create(
            user=other_fisher,
            phone='0700066666',
            landing_site='Kisumu',
            location='Kisumu',
            contact_details='Dock',
            mpesa_phone='0700066666',
        )
        ChairmanApprovalRequest.objects.create(fisherman=self.fisherman, status='PENDING', notes='Bondo request')
        ChairmanApprovalRequest.objects.create(fisherman=other_fisher, status='PENDING', notes='Kisumu request')

        self.client.login(username='beachchair', password='testpass123')
        response = self.client.get(reverse('fishing:chairman_approval_queue'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'fisher2')
        self.assertNotContains(response, 'otherfisher')
