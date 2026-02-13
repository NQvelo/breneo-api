import json
import base64
from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from django.urls import reverse
from unittest.mock import patch, MagicMock
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from rest_framework.test import APIClient
from app.models import UserSubscription

# Generate a temporary RSA key pair for testing
PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PUBLIC_KEY_PEM = PRIVATE_KEY.public_key().public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo
).decode()

class BOGPaymentTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", email="test@example.com", password="password123")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    @override_settings(BOG_CALLBACK_SECRET_PUBLIC_KEY=PUBLIC_KEY_PEM)
    @patch('app.views.requests.post')
    def test_create_order_view(self, mock_post):
        # Mock BOG Token and Order response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = [
            {"access_token": "fake-token"}, # Result of get_bog_token
            { # Result of creating order
                "id": "fake-order-id",
                "_links": {"redirect": {"href": "https://fake-redirect.url"}}
            }
        ]
        mock_post.return_value = mock_response

        # Mock settings for BOG
        with override_settings(BOG_ORDER_URL="https://api.bog.ge/v1/orders", BOG_TOKEN_URL="https://api.bog.ge/oauth/token"):
            response = self.client.post('/api/bog/create-order/', {})
            
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['order_id'], 'fake-order-id')
        self.assertEqual(response.json()['redirect_url'], 'https://fake-redirect.url')

    @override_settings(BOG_CALLBACK_SECRET_PUBLIC_KEY=PUBLIC_KEY_PEM)
    def test_callback_signature_verification_success(self):
        payload = {"order_status": {"key": "completed"}, "payment_detail": {"parent_order_id": "test-parent-id"}}
        payload_bytes = json.dumps(payload, separators=(',', ':')).encode() # Use compact separators

        # Sign the payload
        signature = PRIVATE_KEY.sign(
            payload_bytes,
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        signature_b64 = base64.b64encode(signature).decode()

        # Create subscription to update
        UserSubscription.objects.create(user=self.user, parent_order_id="test-parent-id", is_active=True)

        # For callback, we DON'T want to be authenticated (BOG is external)
        callback_client = APIClient()
        response = callback_client.post(
            '/api/bog/callback/',
            data=payload_bytes,
            content_type="application/json",
            HTTP_CALLBACK_SIGNATURE=signature_b64
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'ok')
        
        sub = UserSubscription.objects.get(parent_order_id="test-parent-id")
        self.assertTrue(sub.is_active)

    @override_settings(BOG_CALLBACK_SECRET_PUBLIC_KEY=PUBLIC_KEY_PEM)
    def test_callback_signature_verification_failure(self):
        payload = {"order_status": {"key": "completed"}}
        callback_client = APIClient()
        response = callback_client.post(
            '/api/bog/callback/',
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_CALLBACK_SIGNATURE="invalid-signature"
        )
        self.assertEqual(response.status_code, 401)

    @patch('app.views.requests.post')
    def test_perform_automatic_charge(self, mock_post):
        from app.views import perform_automatic_charge
        sub = UserSubscription.objects.create(user=self.user, parent_order_id="test-parent-id", is_active=True)
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = [
            {"access_token": "fake-token"},
            {"id": "new-order-id"}
        ]
        mock_post.return_value = mock_response

        with override_settings(BOG_ORDER_URL="https://api.bog.ge/v1/orders", BOG_TOKEN_URL="https://api.bog.ge/oauth/token"):
            success, result = perform_automatic_charge(sub)
            
        self.assertTrue(success)
        self.assertEqual(result['id'], 'new-order-id')
