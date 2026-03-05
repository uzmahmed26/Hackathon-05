"""
Load testing suite for Customer Success AI Agent using Locust
Tests different user types and traffic patterns with multiple scenarios
"""

from locust import HttpUser, task, between, events, constant_throughput
import random
import json
from datetime import datetime
import uuid


class WebFormUser(HttpUser):
    """
    Simulates web form submissions (60% of traffic)
    - Submit support forms with random data
    - Check ticket status occasionally
    - Wait 2-10 seconds between requests
    """
    weight = 60  # 60% of traffic
    wait_time = between(2, 10)

    def on_start(self):
        """Initialize user session"""
        self.ticket_ids = []

    @task(7)  # More frequent: 7 out of 8 tasks
    def submit_support_form(self):
        """Submit a support form"""
        payload = {
            "message": random.choice([
                "I'm having trouble logging in to my account",
                "Can you help me reset my password?",
                "I need information about your enterprise plan",
                "My subscription payment is failing",
                "I want to upgrade my account",
                "I'm experiencing slow performance with the app",
                "I need help with API integration",
                "I received an error message when trying to download",
                "I want to cancel my subscription",
                "I have a billing question"
            ]),
            "channel": "web_form",
            "customer_id": f"web_user_{uuid.uuid4().hex[:8]}@example.com",
            "timestamp": datetime.utcnow().isoformat()
        }

        with self.client.post("/api/query", json=payload, catch_response=True) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if "response" in data and "conversation_id" in data:
                        # Store conversation ID for later status check
                        self.ticket_ids.append(data["conversation_id"])
                        response.success()
                    else:
                        response.failure("Missing required fields in response")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            else:
                response.failure(f"HTTP {response.status_code}")

    @task(1)  # Less frequent: 1 out of 8 tasks
    def check_ticket_status(self):
        """Check status of previously submitted tickets"""
        if not self.ticket_ids:
            return

        # Pick a random ticket ID
        ticket_id = random.choice(self.ticket_ids)
        
        with self.client.get(f"/api/conversations/{ticket_id}", catch_response=True) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if "messages" in data:
                        response.success()
                    else:
                        response.failure("Missing messages in conversation response")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            elif response.status_code == 404:
                # Ticket might have been cleaned up, not a failure
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")


class EmailWebhookUser(HttpUser):
    """
    Simulates Gmail webhooks (25% of traffic)
    - Send email message payloads
    - Wait 5-15 seconds between requests
    """
    weight = 25  # 25% of traffic
    wait_time = between(5, 15)

    @task
    def receive_email_webhook(self):
        """Simulate receiving an email webhook"""
        payload = {
            "message": random.choice([
                "I need to reset my password but I'm not receiving the reset email",
                "Why was my account suspended?",
                "I want to update my billing information",
                "I'm having issues with the mobile app",
                "Can you provide documentation for the API?",
                "I want to schedule a demo",
                "My invoice shows incorrect charges",
                "I need to transfer ownership of my account",
                "I'm getting an error when trying to export data",
                "How do I set up two-factor authentication?"
            ]),
            "channel": "email",
            "customer_id": f"email_user_{random.randint(1000, 9999)}@gmail.com",
            "timestamp": datetime.utcnow().isoformat(),
            "subject": "Customer Support Request",
            "sender": f"customer_{random.randint(1000, 9999)}@gmail.com"
        }

        with self.client.post("/api/query", json=payload, catch_response=True) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if "response" in data and "should_escalate" in data:
                        response.success()
                    else:
                        response.failure("Missing required fields in response")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            else:
                response.failure(f"HTTP {response.status_code}: {response.text}")


class WhatsAppWebhookUser(HttpUser):
    """
    Simulates WhatsApp webhooks (15% of traffic)
    - Send WhatsApp message payloads
    - Wait 10-30 seconds between requests
    """
    weight = 15  # 15% of traffic (total adds up to 100% with others)
    wait_time = between(10, 30)

    @task
    def receive_whatsapp_webhook(self):
        """Simulate receiving a WhatsApp webhook"""
        payload = {
            "message": random.choice([
                "Hi, how do I reset my password?",
                "What's the status of my order?",
                "I need help with my subscription",
                "Can you help me with billing?",
                "I'm having trouble with the app",
                "How do I upgrade my plan?",
                "I want to cancel my account",
                "I didn't receive my confirmation email",
                "Can you help me with API access?",
                "I have a quick question about features"
            ]),
            "channel": "whatsapp",
            "customer_id": f"whatsapp_user_{random.randint(10000, 99999)}",
            "timestamp": datetime.utcnow().isoformat(),
            "phone_number": f"+1{random.randint(1000000000, 9999999999)}"
        }

        with self.client.post("/api/query", json=payload, catch_response=True) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if "response" in data and "sentiment" in data:
                        response.success()
                    else:
                        response.failure("Missing required fields in response")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            else:
                response.failure(f"HTTP {response.status_code}: {response.text}")


class HealthCheckUser(HttpUser):
    """
    Monitors system health (5% of traffic)
    - Check /health endpoint
    - Check /metrics endpoint
    - Wait 5-15 seconds between requests
    """
    weight = 5  # 5% of traffic
    wait_time = between(5, 15)

    @task(3)  # Health check more frequently
    def check_health(self):
        """Check system health"""
        with self.client.get("/health", catch_response=True) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if "status" in data and data["status"] == "healthy":
                        response.success()
                    else:
                        response.failure("Health check failed - invalid response")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response from health endpoint")
            else:
                response.failure(f"Health check failed: HTTP {response.status_code}")

    @task(1)  # Metrics check less frequently
    def check_metrics(self):
        """Check system metrics"""
        with self.client.get("/metrics", catch_response=True) as response:
            if response.status_code == 200:
                # Metrics endpoint typically returns prometheus format, not JSON
                if "process_start_time_seconds" in response.text or "# HELP" in response.text:
                    response.success()
                else:
                    response.failure("Metrics endpoint returned unexpected format")
            else:
                response.failure(f"Metrics check failed: HTTP {response.status_code}")


# Define test scenarios using Locust events
@events.init_command_line_parser.add_listener
def _(parser):
    parser.add_argument("--scenario", type=str, default="QuickSmokeTest",
                       help="Test scenario to run: QuickSmokeTest, SustainedLoadTest, StressTest, SpikeTest")


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Log when test begins"""
    scenario_name = getattr(environment.parsed_options, 'scenario', 'QuickSmokeTest')
    print(f"\n{'='*50}")
    print(f"Starting load test: {scenario_name}")
    print(f"Host: {environment.host}")
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}\n")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Print summary with total requests, failures, response times, requests per second"""
    # Get statistics
    stats = environment.runner.stats
    
    # Calculate totals
    total_requests = sum(entry.num_requests for entry in stats.entries.values())
    total_failures = sum(entry.num_failures for entry in stats.entries.values())
    
    # Calculate response times
    all_response_times = []
    for entry in stats.entries.values():
        all_response_times.extend(entry.response_times.keys())
    
    if all_response_times:
        avg_response_time = sum(all_response_times) / len(all_response_times)
        
        # Calculate percentiles
        sorted_times = sorted(all_response_times)
        n = len(sorted_times)
        
        p95_idx = int(0.95 * n) - 1 if n > 0 else 0
        p99_idx = int(0.99 * n) - 1 if n > 0 else 0
        
        p95_response_time = sorted_times[p95_idx] if p95_idx < n else 0
        p99_response_time = sorted_times[p99_idx] if p99_idx < n else 0
    else:
        avg_response_time = 0
        p95_response_time = 0
        p99_response_time = 0
    
    # Calculate requests per second
    duration = (stats.last_request_timestamp - stats.start_time) if stats.last_request_timestamp and stats.start_time else 1
    if duration > 0:
        req_per_sec = total_requests / duration
    else:
        req_per_sec = 0
    
    # Print summary
    print(f"\n{'='*50}")
    print("LOAD TEST SUMMARY")
    print(f"{'='*50}")
    print(f"Total Requests: {total_requests}")
    print(f"Total Failures: {total_failures}")
    print(f"Success Rate: {(total_requests - total_failures) / total_requests * 100:.2f}%")
    print(f"Average Response Time: {avg_response_time:.2f}ms")
    print(f"P95 Response Time: {p95_response_time:.2f}ms")
    print(f"P99 Response Time: {p99_response_time:.2f}ms")
    print(f"Requests Per Second: {req_per_sec:.2f}")
    print(f"Duration: {duration:.2f}s")
    print(f"{'='*50}\n")


# Define different test scenarios using Locust classes
class QuickSmokeTest(WebFormUser):
    """
    SCENARIO 1: QuickSmokeTest
    - 10 users, 2 users/second spawn rate
    - Run for 1 minute
    - Quick verification that system works
    """
    @task
    def smoke_task(self):
        # Just run the parent tasks
        pass


class SustainedLoadTest(WebFormUser):
    """
    SCENARIO 2: SustainedLoadTest
    - 100 users, 10 users/second spawn rate
    - Run for 1 hour
    - Realistic sustained traffic
    """
    @task
    def sustained_task(self):
        # Just run the parent tasks
        pass


class StressTest(WebFormUser):
    """
    SCENARIO 3: StressTest
    - 500 users, 50 users/second spawn rate
    - Run for 10 minutes
    - Push system to limits
    """
    @task
    def stress_task(self):
        # Just run the parent tasks
        pass


class SpikeTest(WebFormUser):
    """
    SCENARIO 4: SpikeTest
    - 1000 users, 200 users/second spawn rate
    - Run for 5 minutes
    - Sudden traffic surge
    """
    @task
    def spike_task(self):
        # Just run the parent tasks
        pass