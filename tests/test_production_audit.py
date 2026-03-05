"""
Production Audit Tests
======================
Validates every change made during the CRM Digital FTE Factory audit:

1. Database Refinement  — product-docs indexer chunking logic
2. Identity Resolution  — cross-channel customer linking (WhatsApp-first → Email)
3. Agent Tools          — format_for_channel public API + strict Pydantic models
4. Kafka Orchestration  — _consume_messages uses FTEKafkaConsumer
5. K8s / HPA            — hpa.yaml completeness check
"""

import json
import re
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
import yaml  # pyyaml ships with most Python envs; installed via requirements


# ════════════════════════════════════════════════════════════════════════════════
# 1. Product-docs indexer
# ════════════════════════════════════════════════════════════════════════════════

class TestProductDocsIndexer:
    """Chunking logic in scripts/index_product_docs.py — no DB / network needed."""

    @pytest.fixture(autouse=True)
    def import_indexer(self):
        import importlib.util, sys
        spec = importlib.util.spec_from_file_location(
            "index_product_docs",
            Path(__file__).parent.parent / "scripts" / "index_product_docs.py",
        )
        mod = importlib.util.module_from_spec(spec)
        sys.modules["index_product_docs"] = mod
        spec.loader.exec_module(mod)
        self.chunk_markdown = mod.chunk_markdown
        self.detect_category = mod._detect_category

    def test_chunks_product_docs(self):
        docs_path = Path(__file__).parent.parent / "context" / "product-docs.md"
        text = docs_path.read_text(encoding="utf-8")
        chunks = list(self.chunk_markdown(text))
        # product-docs.md has 25 FAQ entries
        assert len(chunks) >= 20, f"Expected ≥20 chunks, got {len(chunks)}"

    def test_chunk_has_title_and_content(self):
        sample = "### 1. How do I create a new account?\nVisit our website and click Sign Up."
        chunks = list(self.chunk_markdown(sample))
        assert len(chunks) == 1
        assert "1. How do I create a new account?" in chunks[0]["title"]
        assert "Visit" in chunks[0]["content"]

    def test_chunk_category_getting_started(self):
        heading = "How do I create a new account?"
        assert self.detect_category(heading) == "getting_started"

    def test_chunk_category_pricing(self):
        heading = "What's included in the Starter Plan?"
        assert self.detect_category(heading) == "pricing"

    def test_chunk_category_troubleshooting(self):
        heading = "My notifications aren't working properly. How do I fix this?"
        assert self.detect_category(heading) == "troubleshooting"

    def test_no_empty_chunks(self):
        docs_path = Path(__file__).parent.parent / "context" / "product-docs.md"
        text = docs_path.read_text(encoding="utf-8")
        chunks = list(self.chunk_markdown(text))
        for c in chunks:
            assert c["title"].strip(), "Empty title in chunk"
            assert c["content"].strip(), f"Empty content for chunk '{c['title']}'"


# ════════════════════════════════════════════════════════════════════════════════
# 2. Identity Resolution — cross-channel linking
# ════════════════════════════════════════════════════════════════════════════════

class TestCrossChannelIdentityResolution:
    """
    Tests the NEW resolve_customer path:
    WhatsApp-first customer contacts via email later → same customer_id.
    Requires a running PostgreSQL instance (docker-compose up -d).
    """

    @pytest.mark.asyncio
    async def test_whatsapp_first_then_email_same_customer(self, db_conn):
        """
        Scenario:
          1. Customer contacts via WhatsApp (phone only) → new customer created,
             stored in customer_identifiers as 'whatsapp'.
          2. Same person later sends an email → resolve_customer must return
             the SAME customer_id (cross-channel resolution via step 2).
        """
        from workers.message_processor import UnifiedMessageProcessor

        worker = UnifiedMessageProcessor()
        worker.db_manager.pool = db_conn._con

        # Step 1 — WhatsApp message (no email)
        wa_msg = {
            "channel": "whatsapp",
            "customer_phone": "+15550001111",
            "customer_name": "WA First User",
        }
        wa_customer_id = await worker.resolve_customer(wa_msg)
        assert isinstance(wa_customer_id, str)

        # Step 2 — Email message (no phone, but same person)
        # We simulate this by inserting an email identifier for the same customer
        # (as would happen if they register with the same email on another channel)
        # Then let the second lookup find it via customer_identifiers
        await db_conn.execute(
            """
            INSERT INTO customer_identifiers (customer_id, identifier_type, identifier_value)
            VALUES ($1, 'email', $2)
            ON CONFLICT (identifier_type, identifier_value) DO NOTHING
            """,
            UUID(wa_customer_id),
            "wafirst@example.com",
        )

        email_msg = {
            "channel": "email",
            "customer_email": "wafirst@example.com",
            "customer_name": "WA First User",
        }
        email_customer_id = await worker.resolve_customer(email_msg)

        assert email_customer_id == wa_customer_id, (
            "Cross-channel resolution failed: WhatsApp and email customer should be the same"
        )

    @pytest.mark.asyncio
    async def test_email_first_then_whatsapp_links(self, db_conn):
        """Email-first customer sends a WhatsApp message — phone must be linked."""
        from workers.message_processor import UnifiedMessageProcessor

        worker = UnifiedMessageProcessor()
        worker.db_manager.pool = db_conn._con

        email_msg = {
            "channel": "email",
            "customer_email": "emailfirst@example.com",
            "customer_name": "Email First",
        }
        email_id = await worker.resolve_customer(email_msg)

        wa_msg = {
            "channel": "whatsapp",
            "customer_email": "emailfirst@example.com",
            "customer_phone": "+15559998888",
            "customer_name": "Email First",
        }
        wa_id = await worker.resolve_customer(wa_msg)

        assert email_id == wa_id

        identifiers = await db_conn.fetch(
            "SELECT identifier_type FROM customer_identifiers WHERE customer_id = $1",
            UUID(email_id),
        )
        types = {r["identifier_type"] for r in identifiers}
        assert "email" in types
        assert "whatsapp" in types

    @pytest.mark.asyncio
    async def test_phone_only_lookup_unchanged(self, db_conn):
        """Original phone-only path still works after refactor."""
        from workers.message_processor import UnifiedMessageProcessor

        customer_id = await db_conn.fetchval(
            "INSERT INTO customers (name) VALUES ($1) RETURNING id",
            "Phone Only",
        )
        await db_conn.execute(
            """
            INSERT INTO customer_identifiers (customer_id, identifier_type, identifier_value)
            VALUES ($1, 'whatsapp', $2)
            """,
            customer_id,
            "+15550002222",
        )

        worker = UnifiedMessageProcessor()
        worker.db_manager.pool = db_conn._con

        resolved = await worker.resolve_customer({"customer_phone": "+15550002222"})
        assert resolved == str(customer_id)

    @pytest.mark.asyncio
    async def test_no_duplicate_customer_on_same_email(self, db_conn):
        """Calling resolve_customer twice with same email → same customer_id."""
        from workers.message_processor import UnifiedMessageProcessor

        worker = UnifiedMessageProcessor()
        worker.db_manager.pool = db_conn._con

        msg = {"customer_email": "idempotent@example.com", "customer_name": "Idempotent"}
        id1 = await worker.resolve_customer(msg)
        id2 = await worker.resolve_customer(msg)
        assert id1 == id2

        count = await db_conn.fetchval(
            "SELECT COUNT(*) FROM customers WHERE email = $1",
            "idempotent@example.com",
        )
        assert count == 1


# ════════════════════════════════════════════════════════════════════════════════
# 3. Agent Tools — format_for_channel + strict Pydantic
# ════════════════════════════════════════════════════════════════════════════════

class TestFormatForChannel:
    """Tests for the public format_for_channel function."""

    @pytest.fixture(autouse=True)
    def import_tools(self):
        from agent.tools import format_for_channel, Channel
        self.fmt = format_for_channel
        self.Channel = Channel

    def test_email_has_greeting_and_signature(self):
        out = self.fmt("Your issue has been resolved.", "email")
        assert "Dear Customer" in out
        assert "Best regards" in out
        assert "TechCorp AI Support Team" in out

    def test_whatsapp_truncates_to_300(self):
        long_msg = "A" * 400
        out = self.fmt(long_msg, "whatsapp")
        assert len(out) <= 300, f"Full WhatsApp output must be ≤300 chars, got {len(out)}"
        assert "..." in out

    def test_whatsapp_short_message_not_truncated(self):
        short = "Order confirmed!"
        out = self.fmt(short, "whatsapp")
        assert short in out
        assert "..." not in out

    def test_whatsapp_has_human_hint(self):
        out = self.fmt("Hello.", "whatsapp")
        assert "human" in out.lower()

    def test_web_form_has_portal_link(self):
        out = self.fmt("Here is your answer.", "web_form")
        assert "support portal" in out.lower()

    def test_private_alias_still_works(self):
        from agent.tools import _format_for_channel
        out = _format_for_channel("test", "email")
        assert "Dear Customer" in out


class TestStrictPydanticModels:
    """Ensure Pydantic models reject wrong types when strict=True."""

    def test_knowledge_search_input_rejects_wrong_type(self):
        from pydantic import ValidationError
        from agent.tools import KnowledgeSearchInput
        with pytest.raises(ValidationError):
            # max_results must be int, not str — strict mode rejects coercion
            KnowledgeSearchInput(query="help", max_results="five")

    def test_ticket_input_requires_valid_channel(self):
        from pydantic import ValidationError
        from agent.tools import TicketInput
        with pytest.raises(ValidationError):
            TicketInput(customer_id="abc", issue="broken", channel="fax")

    def test_response_input_valid(self):
        from agent.tools import ResponseInput, Channel
        r = ResponseInput(
            ticket_id="t1",
            message="Hello",
            channel=Channel.WHATSAPP,
        )
        assert r.channel == Channel.WHATSAPP


# ════════════════════════════════════════════════════════════════════════════════
# 4. Kafka Orchestration
# ════════════════════════════════════════════════════════════════════════════════

class TestKafkaOrchestration:
    """Verify _consume_messages wires up FTEKafkaConsumer correctly."""

    @pytest.mark.asyncio
    async def test_consume_messages_uses_fte_kafka_consumer(self):
        """
        _consume_messages should instantiate FTEKafkaConsumer with the
        'fte.tickets.incoming' topic and call consume().
        """
        from workers.message_processor import UnifiedMessageProcessor

        worker = UnifiedMessageProcessor()
        worker.running = True  # allow entry into the loop

        started = []
        consumed = []
        stopped = []

        class MockConsumer:
            async def start(self):
                started.append(True)

            async def consume(self, handler, error_topic=None):
                consumed.append((handler, error_topic))
                # Stop the loop after first consume call
                worker.running = False

            async def stop(self):
                stopped.append(True)

        with patch("workers.message_processor.FTEKafkaConsumer", return_value=MockConsumer()):
            await worker._consume_messages()

        assert len(started) == 1, "FTEKafkaConsumer.start() should be called once"
        assert len(consumed) == 1, "consume() should be called once"
        handler_fn, dlq_topic = consumed[0]
        assert handler_fn == worker.process_message
        assert dlq_topic is not None  # DLQ topic should be passed

    @pytest.mark.asyncio
    async def test_consume_messages_reconnects_on_error(self):
        """On Kafka error, _consume_messages should retry (loop again)."""
        from workers.message_processor import UnifiedMessageProcessor

        worker = UnifiedMessageProcessor()
        call_count = 0

        class FlakyConsumer:
            async def start(self):
                nonlocal call_count
                call_count += 1
                if call_count < 3:
                    raise ConnectionError("Kafka unavailable")
                worker.running = False  # stop after third attempt

            async def consume(self, **_):
                pass

            async def stop(self):
                pass

        worker.running = True
        with patch("workers.message_processor.FTEKafkaConsumer", return_value=FlakyConsumer()):
            with patch("asyncio.sleep", new_callable=AsyncMock):  # skip sleep
                await worker._consume_messages()

        assert call_count >= 3, "Should have retried at least 3 times"

    def test_kafka_topic_name_is_correct(self):
        """fte.tickets.incoming must be the topic used."""
        from kafka_client import TOPICS
        assert TOPICS["tickets_incoming"] == "fte.tickets.incoming"


# ════════════════════════════════════════════════════════════════════════════════
# 5. K8s HPA completeness
# ════════════════════════════════════════════════════════════════════════════════

class TestHPAManifest:
    """Parse k8s/hpa.yaml and assert production requirements."""

    @pytest.fixture(autouse=True)
    def load_hpa(self):
        hpa_path = Path(__file__).parent.parent / "k8s" / "hpa.yaml"
        text = hpa_path.read_text(encoding="utf-8")
        self.docs = list(yaml.safe_load_all(text))
        assert len(self.docs) == 2, "hpa.yaml should have 2 HPA documents (api + worker)"
        by_name = {d["metadata"]["name"]: d for d in self.docs}
        self.api_hpa = by_name["fte-api-hpa"]
        self.worker_hpa = by_name["fte-worker-hpa"]

    def test_api_cpu_threshold_70(self):
        metrics = self.api_hpa["spec"]["metrics"]
        cpu = next(m for m in metrics if m["resource"]["name"] == "cpu")
        assert cpu["resource"]["target"]["averageUtilization"] == 70

    def test_worker_cpu_threshold_70(self):
        metrics = self.worker_hpa["spec"]["metrics"]
        cpu = next(m for m in metrics if m["resource"]["name"] == "cpu")
        assert cpu["resource"]["target"]["averageUtilization"] == 70

    def test_api_min_max_replicas(self):
        spec = self.api_hpa["spec"]
        assert spec["minReplicas"] == 3
        assert spec["maxReplicas"] == 20

    def test_worker_min_max_replicas(self):
        spec = self.worker_hpa["spec"]
        assert spec["minReplicas"] == 3
        assert spec["maxReplicas"] == 30

    def test_worker_scale_down_policy_present(self):
        behavior = self.worker_hpa["spec"]["behavior"]
        assert "scaleDown" in behavior
        assert behavior["scaleDown"]["stabilizationWindowSeconds"] == 300
        policies = behavior["scaleDown"]["policies"]
        assert len(policies) >= 1

    def test_api_scale_down_stabilization_300(self):
        behavior = self.api_hpa["spec"]["behavior"]
        assert behavior["scaleDown"]["stabilizationWindowSeconds"] == 300

    def test_namespace_correct(self):
        for doc in self.docs:
            assert doc["metadata"]["namespace"] == "customer-success-fte"
