"""
M-Pesa Daraja API Integration Service
Handles OAuth, STK Push, and Payment Callbacks
"""
import json
import logging
import requests
from datetime import datetime
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


class MpesaService:
    """Service class for M-Pesa Daraja API integration"""
    
    def __init__(self):
        self.consumer_key = getattr(settings, 'MPESA_CONSUMER_KEY', '')
        self.consumer_secret = getattr(settings, 'MPESA_CONSUMER_SECRET', '')
        self.business_short_code = getattr(settings, 'MPESA_BUSINESS_SHORT_CODE', '')
        self.passkey = getattr(settings, 'MPESA_PASSKEY', '')
        self.callback_url = getattr(settings, 'MPESA_CALLBACK_URL', '')
        self.base_url = getattr(settings, 'MPESA_BASE_URL', 'https://sandbox.safaricom.co.ke')
        self.access_token = None
        self.token_expiry = None
    
    def get_access_token(self):
        """
        Generate OAuth access token for M-Pesa API
        Returns: access token string or None if failed
        """
        # Check if we have a valid cached token
        if self.access_token and self.token_expiry and timezone.now() < self.token_expiry:
            return self.access_token
        
        try:
            url = f"{self.base_url}/oauth/v1/generate?grant_type=client_credentials"
            response = requests.get(url, auth=(self.consumer_key, self.consumer_secret))
            
            if response.status_code == 200:
                data = response.json()
                self.access_token = data.get('access_token')
                # Set expiry to 50 minutes from now (tokens are valid for 1 hour)
                from datetime import timedelta
                self.token_expiry = timezone.now() + timedelta(minutes=50)
                logger.info("M-Pesa access token generated successfully")
                return self.access_token
            else:
                logger.error(f"Failed to get access token: {response.text}")
                return None
        except Exception as e:
            logger.error(f"Error getting M-Pesa access token: {str(e)}")
            return None
    
    def stk_push(
        self,
        phone_number,
        amount,
        order_number,
        account_reference,
        business_shortcode=None,
        transaction_type="CustomerPayBillOnline",
    ):
        """
        Initiate STK Push request to customer's phone
        Args:
            phone_number: Customer's phone number (format: 254XXXXXXXXX)
            amount: Amount to charge (KES)
            order_number: Order reference
            account_reference: Account reference for the transaction
        Returns:
            dict with response data or error
        """
        access_token = self.get_access_token()
        if not access_token:
            return {'success': False, 'error': 'Failed to get access token'}
        
        try:
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            password = self.generate_password(timestamp)
            
            shortcode = business_shortcode or self.business_short_code
            payload = {
                "BusinessShortCode": shortcode,
                "Password": password,
                "Timestamp": timestamp,
                "TransactionType": transaction_type,
                "Amount": str(int(amount)),
                "PartyA": phone_number,
                "PartyB": shortcode,
                "PhoneNumber": phone_number,
                "CallBackURL": self.callback_url,
                "AccountReference": account_reference,
                "TransactionDesc": f"Payment for Order #{order_number}"
            }
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            url = f"{self.base_url}/mpesa/stkpush/v1/processrequest"
            response = requests.post(url, json=payload, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"STK Push initiated successfully for Order #{order_number}")
                return {
                    'success': True,
                    'merchant_request_id': data.get('MerchantRequestID'),
                    'checkout_request_id': data.get('CheckoutRequestID'),
                    'response_code': data.get('ResponseCode'),
                    'response_message': data.get('ResponseDescription'),
                    'customer_message': data.get('CustomerMessage')
                }
            else:
                error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
                logger.error(f"STK Push failed: {response.text}")
                return {
                    'success': False,
                    'error': error_data.get('errorMessage', 'STK Push request failed'),
                    'response_code': response.status_code
                }
        except Exception as e:
            logger.error(f"Error initiating STK Push: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def generate_password(self, timestamp):
        """Generate M-Pesa API password"""
        data = f"{self.business_short_code}{self.passkey}{timestamp}"
        import base64
        return base64.b64encode(data.encode()).decode()
    
    def query_stk_status(self, checkout_request_id):
        """
        Query the status of an STK Push request
        Args:
            checkout_request_id: The CheckoutRequestID from STK Push
        Returns:
            dict with transaction status
        """
        access_token = self.get_access_token()
        if not access_token:
            return {'success': False, 'error': 'Failed to get access token'}
        
        try:
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            password = self.generate_password(timestamp)
            
            payload = {
                "BusinessShortCode": self.business_short_code,
                "Password": password,
                "Timestamp": timestamp,
                "CheckoutRequestID": checkout_request_id
            }
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            url = f"{self.base_url}/mpesa/stkpushquery/v1/query"
            response = requests.post(url, json=payload, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'success': True,
                    'response_code': data.get('ResponseCode'),
                    'response_message': data.get('ResponseDescription'),
                    'result_code': data.get('ResultCode'),
                    'result_desc': data.get('ResultDesc'),
                    'amount': data.get('Amount'),
                    'mpesa_receipt_number': data.get('MpesaReceiptNumber'),
                    'transaction_date': data.get('TransactionDate'),
                    'phone_number': data.get('PhoneNumber')
                }
            else:
                return {
                    'success': False,
                    'error': 'Failed to query STK status'
                }
        except Exception as e:
            logger.error(f"Error querying STK status: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def b2c_payment(self, phone_number, amount, remarks):
        """
        Send payment to customer (Business to Customer)
        Used for refunds
        Args:
            phone_number: Customer's phone number
            amount: Amount to send (KES)
            remarks: Transaction remarks
        Returns:
            dict with response
        """
        access_token = self.get_access_token()
        if not access_token:
            return {'success': False, 'error': 'Failed to get access token'}
        
        try:
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            password = self.generate_password(timestamp)
            
            payload = {
                "InitiatorName": getattr(settings, 'MPESA_INITIATOR_NAME', ''),
                "SecurityCredential": getattr(settings, 'MPESA_SECURITY_CREDENTIAL', ''),
                "CommandID": "BusinessPayment",
                "Amount": str(int(amount)),
                "PartyA": self.business_short_code,
                "PartyB": phone_number,
                "Remarks": remarks,
                "QueueTimeOutURL": f"{self.callback_url}/b2c/timeout",
                "ResultURL": f"{self.callback_url}/b2c/result",
                "Occasion": "Refund"
            }
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            url = f"{self.base_url}/mpesa/b2c/v1/paymentrequest"
            response = requests.post(url, json=payload, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'success': True,
                    'conversation_id': data.get('ConversationID'),
                    'originator_conversation_id': data.get('OriginatorConversationID'),
                    'response_code': data.get('ResponseCode')
                }
            else:
                return {
                    'success': False,
                    'error': 'B2C payment failed'
                }
        except Exception as e:
            logger.error(f"Error with B2C payment: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def parse_callback_data(raw_data):
        """
        Parse M-Pesa callback data
        Args:
            raw_data: Raw JSON data from callback
        Returns:
            dict with parsed transaction details
        """
        try:
            data = json.loads(raw_data)
            stk_callback = data.get('Body', {}).get('stkCallback', {})
            
            result_code_raw = stk_callback.get('ResultCode')
            try:
                result_code = int(result_code_raw)
            except (TypeError, ValueError):
                result_code = -1
            result_desc = stk_callback.get('ResultDesc')
            
            # Check if transaction was successful
            if result_code == 0:
                callback_metadata = stk_callback.get('CallbackMetadata', {})
                items = callback_metadata.get('Item', [])
                
                metadata = {}
                for item in items:
                    name = item.get('Name')
                    value = item.get('Value')
                    if name and value:
                        metadata[name] = value
                
                return {
                    'success': True,
                    'transaction_id': metadata.get('MpesaReceiptNumber'),
                    'amount': metadata.get('Amount'),
                    'phone_number': metadata.get('PhoneNumber'),
                    'transaction_date': metadata.get('TransactionDate'),
                    'result_code': result_code,
                    'result_desc': result_desc,
                    'merchant_request_id': stk_callback.get('MerchantRequestID'),
                    'checkout_request_id': stk_callback.get('CheckoutRequestID')
                }
            else:
                return {
                    'success': False,
                    'result_code': result_code,
                    'result_desc': result_desc,
                    'merchant_request_id': stk_callback.get('MerchantRequestID'),
                    'checkout_request_id': stk_callback.get('CheckoutRequestID')
                }
        except Exception as e:
            logger.error(f"Error parsing M-Pesa callback: {str(e)}")
            return {
                'success': False,
                'error': f'Failed to parse callback: {str(e)}'
            }


# Convenience function for using M-Pesa service
def initiate_stk_push(
    phone_number,
    amount,
    order_number,
    business_shortcode=None,
    account_reference=None,
    transaction_type="CustomerPayBillOnline",
):
    """
    Convenience function to initiate STK Push
    Args:
        phone_number: Customer phone number
        amount: Payment amount in KES
        order_number: Order reference number
    Returns:
        dict with response
    """
    mpesa = MpesaService()
    
    # Format phone number
    if phone_number.startswith('0'):
        phone_number = '254' + phone_number[1:]
    elif not phone_number.startswith('254'):
        phone_number = '254' + phone_number
    
    # Account reference is the order number unless explicitly provided.
    account_reference = account_reference or f"ORDER{order_number}"
    return mpesa.stk_push(
        phone_number,
        amount,
        order_number,
        account_reference,
        business_shortcode=business_shortcode,
        transaction_type=transaction_type,
    )


def process_payment_callback(raw_data):
    """
    Process M-Pesa payment callback
    Args:
        raw_data: Raw JSON data from callback
    Returns:
        dict with processed transaction details
    """
    logger.info("M-Pesa Payment Callback - Raw Data: %s", raw_data)
    return MpesaService.parse_callback_data(raw_data)
