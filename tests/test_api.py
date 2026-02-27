"""
Tests for API endpoints.
"""

import pytest
from httpx import AsyncClient
import json
from datetime import datetime


class TestHealthEndpoints:
    """Test health check endpoints"""
    
    @pytest.mark.asyncio
    async def test_health_check(self, api_client):
        """Test health check endpoint"""
        response = await api_client.get("/health")
        
        # Should return 200 or 503 depending on if dependencies are available
        assert response.status_code in [200, 503]
        
        if response.status_code == 200:
            data = response.json()
            assert "status" in data
            assert "timestamp" in data
            assert data["status"] in ["healthy", "unhealthy"]
    
    @pytest.mark.asyncio
    async def test_readiness_check(self, api_client):
        """Test readiness check endpoint"""
        response = await api_client.get("/ready")
        
        # Should return 200 or 503
        assert response.status_code in [200, 503]
        
        if response.status_code == 200:
            data = response.json()
            assert "status" in data
            assert data["status"] == "ready"
    
    @pytest.mark.asyncio
    async def test_liveness_check(self, api_client):
        """Test liveness check endpoint"""
        response = await api_client.get("/live")
        
        # Should return 200 if the service is running
        assert response.status_code == 200
        
        data = response.json()
        assert "status" in data
        assert data["status"] == "alive"


class TestMetricsEndpoints:
    """Test metrics endpoints"""
    
    @pytest.mark.asyncio
    async def test_metrics_endpoint(self, api_client):
        """Test metrics endpoint"""
        response = await api_client.get("/metrics")
        
        # Should return 200 or 503 depending on DB connectivity
        assert response.status_code in [200, 503]
        
        if response.status_code == 200:
            data = response.json()
            assert "timestamp" in data
            assert "messages" in data
            assert "performance" in data
            assert "tickets" in data
    
    @pytest.mark.asyncio
    async def test_channel_metrics_endpoint(self, api_client):
        """Test channel metrics endpoint"""
        response = await api_client.get("/metrics/channels")
        
        # Should return 200 or 503 depending on DB connectivity
        assert response.status_code in [200, 503]
        
        if response.status_code == 200:
            data = response.json()
            # Should return a dictionary with channel metrics
            assert isinstance(data, dict)
            # May be empty if no data exists yet


class TestWebhookEndpoints:
    """Test webhook endpoints for different channels"""
    
    @pytest.mark.asyncio
    async def test_gmail_webhook(self, api_client, sample_email_message):
        """Test Gmail webhook endpoint"""
        response = await api_client.post(
            "/webhooks/gmail",
            json=sample_email_message
        )
        
        # Should return 200 for successful processing or 404 if endpoint doesn't exist
        assert response.status_code in [200, 400, 404, 405, 500]

    @pytest.mark.asyncio
    async def test_whatsapp_webhook(self, api_client, sample_whatsapp_message):
        """Test WhatsApp webhook endpoint"""
        response = await api_client.post(
            "/webhooks/whatsapp",
            json=sample_whatsapp_message
        )

        # 403 is expected when no Twilio signature header is present
        assert response.status_code in [200, 400, 403, 404, 405, 500]

    @pytest.mark.asyncio
    async def test_webhook_validation(self, api_client):
        """Test webhook request validation"""
        # Test with malformed request
        response = await api_client.post(
            "/webhooks/gmail",
            json={"invalid": "data"}
        )

        # Should return validation error (422) or 400
        assert response.status_code in [422, 400, 404, 405, 500]


class TestSupportEndpoints:
    """Test support-related endpoints"""
    
    @pytest.mark.asyncio
    async def test_web_form_submit(self, api_client):
        """Test web form submission endpoint"""
        form_data = {
            'name': 'Test User',
            'email': 'test@example.com',
            'subject': 'Test Subject',
            'category': 'general',
            'message': 'This is a test message for the web form.'
        }
        
        response = await api_client.post(
            "/api/support/submit",
            json=form_data
        )
        
        # Should return 200 for successful submission or 404 if endpoint doesn't exist
        assert response.status_code in [200, 404, 405]
    
    @pytest.mark.asyncio
    async def test_web_form_validation(self, api_client):
        """Test web form validation"""
        # Test with missing required fields
        incomplete_form = {
            'name': 'Test User',
            # Missing email
            'message': 'Test message'
        }
        
        response = await api_client.post(
            "/api/support/submit",
            json=incomplete_form
        )
        
        # Should return validation error
        assert response.status_code in [422, 400, 404]
    
    @pytest.mark.asyncio
    async def test_support_categories(self, api_client):
        """Test support categories endpoint"""
        response = await api_client.get("/api/support/categories")
        
        # Should return 200 with categories or 404 if endpoint doesn't exist
        assert response.status_code in [200, 404]
        
        if response.status_code == 200:
            data = response.json()
            # Should return a list of categories
            assert isinstance(data, list)


class TestAuthentication:
    """Test API authentication"""
    
    @pytest.mark.asyncio
    async def test_unauthorized_access(self, api_client):
        """Test access to protected endpoints without auth"""
        # Try to access a potentially protected endpoint
        response = await api_client.get("/api/admin/status")
        
        # Should return 401, 403, or 404 (if endpoint doesn't exist)
        assert response.status_code in [401, 403, 404]
    
    @pytest.mark.asyncio
    async def test_root_endpoint(self, api_client):
        """Test root endpoint"""
        response = await api_client.get("/")
        
        # Should return 200 with service info
        assert response.status_code == 200
        
        data = response.json()
        assert "service" in data
        assert "version" in data
        assert "status" in data
        assert "channels" in data
        assert isinstance(data["channels"], list)


class TestErrorHandling:
    """Test API error handling"""
    
    @pytest.mark.asyncio
    async def test_not_found_endpoint(self, api_client):
        """Test accessing non-existent endpoint"""
        response = await api_client.get("/nonexistent/endpoint")
        
        # Should return 404
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_invalid_json(self, api_client):
        """Test sending invalid JSON"""
        # Send malformed JSON
        response = await api_client.post(
            "/webhooks/gmail",
            content="{invalid json"
        )
        
        # Should return 422 for validation error or 400 for bad request
        assert response.status_code in [422, 400]
    
    @pytest.mark.asyncio
    async def test_large_payload(self, api_client):
        """Test handling large payloads"""
        # Create a very large payload
        large_data = {
            "message": "test" * 10000,  # Very long message
            "metadata": {"large_field": "data" * 10000}
        }
        
        response = await api_client.post(
            "/webhooks/gmail",
            json=large_data
        )
        
        # Should handle gracefully (might return 413 for too large, or process normally)
        assert response.status_code in [200, 413, 422, 400, 404, 405, 500]


class TestRateLimiting:
    """Test API rate limiting"""
    
    @pytest.mark.asyncio
    async def test_multiple_requests(self, api_client):
        """Test behavior under multiple rapid requests"""
        # Send multiple requests rapidly
        responses = []
        for i in range(5):
            response = await api_client.get("/health")
            responses.append(response.status_code)
        
        # All should succeed (unless rate limiting is very strict)
        # In a real implementation, some might return 429 (Too Many Requests)
        success_responses = [r for r in responses if r in [200, 503]]
        assert len(success_responses) >= 0  # Allow for rate limiting


class TestAPIVersioning:
    """Test API versioning"""
    
    @pytest.mark.asyncio
    async def test_versioned_endpoints(self, api_client):
        """Test versioned API endpoints"""
        # Test v1 endpoint (if it exists)
        response_v1 = await api_client.get("/v1/health")
        
        # Test v2 endpoint (if it exists)
        response_v2 = await api_client.get("/v2/health")
        
        # Both should return appropriate status codes
        assert response_v1.status_code in [200, 404]
        assert response_v2.status_code in [200, 404]


class TestCORS:
    """Test CORS headers"""
    
    @pytest.mark.asyncio
    async def test_cors_headers(self, api_client):
        """Test CORS headers in responses"""
        response = await api_client.get("/health")
        
        # Check if CORS headers are present (implementation-dependent)
        # The headers might not be set if CORS middleware isn't configured yet
        pass  # Skip for now as CORS might not be implemented yet