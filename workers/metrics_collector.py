"""
Background Metrics Collector Worker
Collects and aggregates agent performance metrics from Kafka.
Stores daily summaries in PostgreSQL for reporting.
"""

import asyncio
import logging
import os
import json
from datetime import datetime, date
from collections import defaultdict

from kafka_client import FTEKafkaConsumer, FTEKafkaProducer, TOPICS

logger = logging.getLogger(__name__)


class MetricsCollector:
    """
    Background worker that consumes metrics events from Kafka
    and stores aggregated data in PostgreSQL.

    Metrics collected:
    - Response latency per channel
    - Escalation rate per channel
    - Message volume per channel
    - Sentiment score distribution
    - Tool call frequency
    """

    def __init__(self):
        self._counters: dict = defaultdict(lambda: defaultdict(float))
        self._counts: dict = defaultdict(lambda: defaultdict(int))
        self._running = False

    async def start(self):
        """Start the metrics collection worker."""
        self._running = True
        logger.info("Metrics collector starting...")

        # Run consumer and periodic flush in parallel
        await asyncio.gather(
            self._consume_metrics(),
            self._periodic_flush(),
        )

    async def _consume_metrics(self):
        """Consume metrics events from Kafka."""
        consumer = FTEKafkaConsumer(
            topics=[TOPICS["metrics"]],
            group_id="fte-metrics-collector",
        )
        await consumer.start()

        try:
            await consumer.consume(self._process_metric)
        finally:
            await consumer.stop()

    async def _process_metric(self, topic: str, event: dict):
        """Process a single metrics event."""
        try:
            event_type = event.get("event_type", "unknown")
            channel = event.get("channel", "unknown")

            if event_type == "message_processed":
                latency = event.get("latency_ms", 0)
                escalated = event.get("escalated", False)

                self._counters[channel]["total_latency_ms"] += latency
                self._counts[channel]["message_count"] += 1

                if escalated:
                    self._counts[channel]["escalation_count"] += 1

                tool_count = event.get("tool_calls_count", 0)
                self._counters[channel]["total_tool_calls"] += tool_count

                logger.debug(
                    f"Metric recorded: {channel} | latency={latency:.0f}ms | "
                    f"escalated={escalated}"
                )

            elif event_type == "processing_error":
                self._counts[channel]["error_count"] += 1

            elif event_type == "escalation":
                self._counts[channel]["escalation_count"] += 1

        except Exception as e:
            logger.error(f"Failed to process metric event: {e}")

    async def _periodic_flush(self):
        """Flush aggregated metrics to database every 60 seconds."""
        while self._running:
            await asyncio.sleep(60)
            await self._flush_to_database()

    async def _flush_to_database(self):
        """Write aggregated metrics to PostgreSQL."""
        try:
            import asyncpg

            dsn = os.getenv(
                "DATABASE_URL",
                "postgresql://fte_user:fte_password@localhost:5432/fte_db",
            )
            conn = await asyncpg.connect(dsn)

            try:
                for channel, counters in self._counters.items():
                    counts = self._counts.get(channel, {})
                    msg_count = counts.get("message_count", 0)
                    escalation_count = counts.get("escalation_count", 0)
                    error_count = counts.get("error_count", 0)

                    if msg_count == 0:
                        continue

                    avg_latency = counters.get("total_latency_ms", 0) / msg_count
                    escalation_rate = escalation_count / msg_count if msg_count > 0 else 0

                    # Write channel metrics
                    metrics_to_write = [
                        ("avg_response_latency_ms", avg_latency, channel),
                        ("message_volume", float(msg_count), channel),
                        ("escalation_rate", escalation_rate, channel),
                        ("error_count", float(error_count), channel),
                    ]

                    for metric_name, metric_value, ch in metrics_to_write:
                        await conn.execute("""
                            INSERT INTO agent_metrics (metric_name, metric_value, channel, recorded_at)
                            VALUES ($1, $2, $3, NOW())
                        """, metric_name, metric_value, ch)

                logger.info(
                    f"Metrics flushed to DB for channels: {list(self._counters.keys())}"
                )

                # Reset counters after flush
                self._counters.clear()
                self._counts.clear()

            finally:
                await conn.close()

        except Exception as e:
            logger.error(f"Metrics flush failed: {e}")

    async def generate_daily_report(self) -> dict:
        """
        Generate a daily summary report of agent performance.
        Returns a dict suitable for sending via email or Slack.
        """
        try:
            import asyncpg

            dsn = os.getenv(
                "DATABASE_URL",
                "postgresql://fte_user:fte_password@localhost:5432/fte_db",
            )
            conn = await asyncpg.connect(dsn)

            try:
                # Get metrics from last 24 hours
                rows = await conn.fetch("""
                    SELECT
                        channel,
                        metric_name,
                        AVG(metric_value) as avg_value,
                        SUM(metric_value) as total_value
                    FROM agent_metrics
                    WHERE recorded_at > NOW() - INTERVAL '24 hours'
                    GROUP BY channel, metric_name
                    ORDER BY channel, metric_name
                """)

                # Conversation summary
                conv_rows = await conn.fetch("""
                    SELECT
                        initial_channel,
                        COUNT(*) as total,
                        COUNT(*) FILTER (WHERE status = 'resolved') as resolved,
                        COUNT(*) FILTER (WHERE status = 'escalated') as escalated,
                        AVG(sentiment_score) as avg_sentiment
                    FROM conversations
                    WHERE started_at > NOW() - INTERVAL '24 hours'
                    GROUP BY initial_channel
                """)

                report = {
                    "date": date.today().isoformat(),
                    "generated_at": datetime.utcnow().isoformat(),
                    "channels": {},
                    "summary": {
                        "total_conversations": 0,
                        "total_resolved": 0,
                        "total_escalated": 0,
                    },
                }

                for row in conv_rows:
                    ch = row["initial_channel"]
                    report["channels"][ch] = {
                        "total_conversations": row["total"],
                        "resolved": row["resolved"],
                        "escalated": row["escalated"],
                        "escalation_rate": (
                            row["escalated"] / row["total"] if row["total"] > 0 else 0
                        ),
                        "avg_sentiment": float(row["avg_sentiment"] or 0),
                    }
                    report["summary"]["total_conversations"] += row["total"]
                    report["summary"]["total_resolved"] += row["resolved"]
                    report["summary"]["total_escalated"] += row["escalated"]

                for row in rows:
                    ch = row["channel"]
                    if ch not in report["channels"]:
                        report["channels"][ch] = {}
                    report["channels"][ch][row["metric_name"]] = {
                        "avg": float(row["avg_value"] or 0),
                        "total": float(row["total_value"] or 0),
                    }

                return report

            finally:
                await conn.close()

        except Exception as e:
            logger.error(f"Daily report generation failed: {e}")
            return {"error": str(e), "date": date.today().isoformat()}


async def main():
    """Main entry point for the metrics collector worker."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    collector = MetricsCollector()
    logger.info("Starting metrics collector worker...")
    await collector.start()


if __name__ == "__main__":
    asyncio.run(main())
