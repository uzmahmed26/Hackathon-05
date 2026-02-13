# Load Testing with Locust

This project includes a comprehensive load testing suite using Locust for performance testing of the Customer Success AI Agent.

## Installation

First, make sure Locust is installed:

```bash
pip install locust
```

## User Classes

The load test suite includes four different user types that simulate real-world traffic:

1. **WebFormUser** (60% of traffic)
   - Simulates web form submissions
   - Submits support forms with random data
   - Checks ticket status occasionally
   - Waits 2-10 seconds between requests

2. **EmailWebhookUser** (25% of traffic)
   - Simulates Gmail webhooks
   - Sends email message payloads
   - Waits 5-15 seconds between requests

3. **WhatsAppWebhookUser** (15% of traffic)
   - Simulates WhatsApp webhooks
   - Sends WhatsApp message payloads
   - Waits 10-30 seconds between requests

4. **HealthCheckUser** (5% of traffic)
   - Monitors system health
   - Checks /health and /metrics endpoints
   - Waits 5-15 seconds between requests

## Test Scenarios

The suite includes four different test scenarios:

### 1. QuickSmokeTest
- 10 users, 2 users/second spawn rate
- Runs for 1 minute
- Quick verification that system works

### 2. SustainedLoadTest
- 100 users, 10 users/second spawn rate
- Runs for 1 hour
- Simulates realistic sustained traffic

### 3. StressTest
- 500 users, 50 users/second spawn rate
- Runs for 10 minutes
- Pushes system to its limits

### 4. SpikeTest
- 1000 users, 200 users/second spawn rate
- Runs for 5 minutes
- Simulates sudden traffic surge

## Running Tests

### Interactive Mode (with Web UI)
```bash
# Navigate to the project directory
cd customer-success-fte

# Run with web UI
locust -f tests/load_test.py --host=http://localhost:8000
```

Then open your browser to http://localhost:8089 to configure and start the test.

### Headless Mode (without Web UI)
```bash
# Run Quick Smoke Test
locust -f tests/load_test.py QuickSmokeTest --headless -u 10 -r 2 -t 1m --host=http://localhost:8000

# Run Sustained Load Test
locust -f tests/load_test.py SustainedLoadTest --headless -u 100 -r 10 -t 1h --host=http://localhost:8000

# Run Stress Test
locust -f tests/load_test.py StressTest --headless -u 500 -r 50 -t 10m --host=http://localhost:8000

# Run Spike Test
locust -f tests/load_test.py SpikeTest --headless -u 1000 -r 200 -t 5m --host=http://localhost:8000
```

## Metrics Collected

During each test, the following metrics are collected and reported:

- Total requests made
- Total failures
- Success rate percentage
- Average response time
- 95th percentile response time
- 99th percentile response time
- Requests per second
- Total test duration

## Configuration

The test scenarios can be customized by modifying the parameters in the `load_test.py` file:

- Adjust user weights to change traffic distribution
- Modify wait times between requests
- Change spawn rates and user counts
- Add new test scenarios as needed