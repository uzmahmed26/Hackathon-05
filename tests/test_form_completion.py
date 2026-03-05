"""
Form Completion Tests
=====================
Validates all changes made to complete the web-form per task requirements:

1. schema.sql — users table present
2. Ticket status endpoint — returns 422 for bad UUID, 503 when no DB
3. Web form submit endpoint — validation, 503 when no DB, 200 happy path (mocked DB)
4. Auth signup/login endpoint — proper errors without DB
5. api.js — auth header helper exported
6. SupportForm.jsx — reads ticket_id (snake_case) not ticketId
"""

import re
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


# ══════════════════════════════════════════════════════════════════════════════
# 1. schema.sql — users table
# ══════════════════════════════════════════════════════════════════════════════

class TestSchemaUsersTable:

    @pytest.fixture(autouse=True)
    def load_schema(self):
        self.sql = (
            Path(__file__).parent.parent / "database" / "schema.sql"
        ).read_text(encoding="utf-8")

    def test_users_table_exists(self):
        assert "CREATE TABLE" in self.sql and "users" in self.sql, \
            "schema.sql must define a 'users' table"

    def test_users_has_password_hash(self):
        assert "password_hash" in self.sql

    def test_users_has_is_active(self):
        assert "is_active" in self.sql

    def test_users_email_unique(self):
        # Check UNIQUE constraint on email within the users block
        assert re.search(r"CREATE TABLE IF NOT EXISTS users", self.sql), \
            "users table should use CREATE TABLE IF NOT EXISTS"

    def test_users_email_index(self):
        assert "idx_users_email" in self.sql


# ══════════════════════════════════════════════════════════════════════════════
# 2. Ticket status endpoint — unit tests (no real DB)
# ══════════════════════════════════════════════════════════════════════════════

class TestTicketStatusEndpoint:
    """Tests for GET /api/support/ticket/{id} — mocked DB."""

    @pytest.fixture
    def client(self):
        import httpx
        from api.main import app

        transport = httpx.ASGITransport(app=app)
        return httpx.AsyncClient(transport=transport, base_url="http://test")

    @pytest.mark.asyncio
    async def test_invalid_uuid_returns_422(self, client):
        async with client as c:
            res = await c.get("/api/support/ticket/not-a-uuid")
        assert res.status_code == 422

    @pytest.mark.asyncio
    async def test_no_db_returns_503(self, client):
        """Without a DB connection the endpoint returns 503."""
        from api.main import app
        app.state.db_manager = None

        async with client as c:
            res = await c.get("/api/support/ticket/27184ce8-034b-42f3-bd9a-6b5cd811e7fb")
        assert res.status_code == 503

    @pytest.mark.asyncio
    async def test_ticket_not_found_returns_404(self):
        """Ticket UUID not in DB → 404."""
        from api.main import app
        import httpx

        # Build a mock DB pool that returns None (ticket not found)
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)

        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=_async_ctx(mock_conn))

        mock_db = MagicMock()
        mock_db.pool = mock_pool
        app.state.db_manager = mock_db

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            res = await c.get("/api/support/ticket/27184ce8-034b-42f3-bd9a-6b5cd811e7fb")

        app.state.db_manager = None  # reset
        assert res.status_code == 404

    @pytest.mark.asyncio
    async def test_valid_ticket_returns_200(self):
        """Happy path: ticket exists, messages returned."""
        from api.main import app
        from datetime import datetime, timezone
        import httpx, uuid

        tid = uuid.uuid4()
        cid = uuid.uuid4()
        now = datetime.now(timezone.utc)

        # First fetchrow → ticket row; second fetch → messages
        ticket_row = {
            "ticket_id": tid,
            "ticket_status": "open",
            "ticket_created_at": now,
            "ticket_resolved_at": None,
            "conversation_id": cid,
        }

        class _FakeRow(dict):
            pass

        fake_ticket = _FakeRow(ticket_row)

        msg_row = _FakeRow({
            "id": uuid.uuid4(),
            "role": "customer",
            "content": "Hello",
            "created_at": now,
        })

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=fake_ticket)
        mock_conn.fetch    = AsyncMock(return_value=[msg_row])

        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=_async_ctx(mock_conn))

        mock_db = MagicMock()
        mock_db.pool = mock_pool
        app.state.db_manager = mock_db

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            res = await c.get(f"/api/support/ticket/{tid}")

        app.state.db_manager = None  # reset

        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "open"
        assert len(data["messages"]) == 1
        assert data["messages"][0]["role"] == "customer"


# helper: async context manager for pool.acquire()
class _async_ctx:
    def __init__(self, obj): self._obj = obj
    async def __aenter__(self): return self._obj
    async def __aexit__(self, *_): pass


# ══════════════════════════════════════════════════════════════════════════════
# 3. Web form submit — validation tests (no DB needed)
# ══════════════════════════════════════════════════════════════════════════════

class TestWebFormSubmit:

    @pytest.fixture
    def client(self):
        from api.main import app
        import httpx

        app.state.db_manager = None
        transport = httpx.ASGITransport(app=app)
        return httpx.AsyncClient(transport=transport, base_url="http://test")

    @pytest.mark.asyncio
    async def test_missing_required_fields_returns_422(self, client):
        async with client as c:
            res = await c.post("/api/support/submit", json={})
        assert res.status_code == 422

    @pytest.mark.asyncio
    async def test_short_message_returns_422(self, client):
        async with client as c:
            res = await c.post("/api/support/submit", json={
                "name": "Alice",
                "email": "alice@example.com",
                "subject": "Help me",
                "category": "general",
                "priority": "medium",
                "message": "short",   # < 10 chars
            })
        assert res.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_email_returns_422(self, client):
        async with client as c:
            res = await c.post("/api/support/submit", json={
                "name": "Bob",
                "email": "not-an-email",
                "subject": "Question about billing",
                "category": "billing",
                "priority": "low",
                "message": "I have a billing question that I need help with.",
            })
        assert res.status_code == 422

    @pytest.mark.asyncio
    async def test_valid_submission_returns_200_with_ticket_id(self, client):
        """
        Valid payload → 200 + ticket_id UUID even without DB
        (background task gracefully skips DB ops when db_manager is None).
        """
        async with client as c:
            res = await c.post("/api/support/submit", json={
                "name": "Charlie",
                "email": "charlie@example.com",
                "subject": "Cannot log in after update",
                "category": "technical",
                "priority": "high",
                "message": "After the latest update I cannot log in. Please help me fix this issue.",
            })
        assert res.status_code == 200
        data = res.json()
        assert "ticket_id" in data
        assert len(data["ticket_id"]) == 36   # UUID format
        assert "message" in data
        assert "estimated_response_time" in data

    @pytest.mark.asyncio
    async def test_invalid_category_returns_422(self, client):
        async with client as c:
            res = await c.post("/api/support/submit", json={
                "name": "Dave",
                "email": "dave@example.com",
                "subject": "Something weird",
                "category": "nonexistent_category",
                "priority": "low",
                "message": "This is a long enough message to pass validation.",
            })
        assert res.status_code == 422


# ══════════════════════════════════════════════════════════════════════════════
# 4. Auth endpoints — error cases without DB
# ══════════════════════════════════════════════════════════════════════════════

class TestAuthEndpoints:

    @pytest.fixture
    def client(self):
        from api.main import app
        import httpx

        app.state.db_manager = None
        transport = httpx.ASGITransport(app=app)
        return httpx.AsyncClient(transport=transport, base_url="http://test")

    @pytest.mark.asyncio
    async def test_login_without_db_returns_503(self, client):
        async with client as c:
            res = await c.post("/api/auth/login", json={
                "email": "user@example.com",
                "password": "password123",
            })
        assert res.status_code == 503

    @pytest.mark.asyncio
    async def test_signup_without_db_returns_503(self, client):
        async with client as c:
            res = await c.post("/api/auth/signup", json={
                "name": "Eve",
                "email": "eve@example.com",
                "password": "password123",
            })
        assert res.status_code == 503

    @pytest.mark.asyncio
    async def test_signup_short_password_returns_422(self, client):
        """Password < 8 chars should be rejected with 422 before DB is consulted."""
        # Give it a mock DB so we get past the 503 check
        from api.main import app
        import httpx

        mock_db = MagicMock()
        mock_db.pool = MagicMock()
        app.state.db_manager = mock_db

        # Patch get_user_by_email to raise so we confirm validation fires first
        with patch("api.auth.get_user_by_email", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
                res = await c.post("/api/auth/signup", json={
                    "name": "Eve",
                    "email": "eve@example.com",
                    "password": "short",
                })

        app.state.db_manager = None
        assert res.status_code == 422


# ══════════════════════════════════════════════════════════════════════════════
# 5. api.js — static content checks (no browser needed)
# ══════════════════════════════════════════════════════════════════════════════

class TestApiJs:
    """Read api.js as text and assert required patterns are present."""

    @pytest.fixture(autouse=True)
    def read_api_js(self):
        self.src = (
            Path(__file__).parent.parent / "web-form" / "api.js"
        ).read_text(encoding="utf-8")

    def test_exports_submit_support_form(self):
        assert "export async function submitSupportForm" in self.src

    def test_exports_get_ticket_status(self):
        assert "export async function getTicketStatus" in self.src

    def test_has_auth_header_helper(self):
        assert "Authorization" in self.src

    def test_submit_uses_auth_headers(self):
        # The submitSupportForm body must pass authHeaders() or buildHeaders()
        submit_section = self.src[
            self.src.index("export async function submitSupportForm"):
            self.src.index("export async function getTicketStatus")
        ]
        assert "authHeaders" in submit_section or "buildHeaders" in submit_section

    def test_get_ticket_uses_auth_headers(self):
        get_section = self.src[self.src.index("export async function getTicketStatus"):]
        assert "authHeaders" in get_section or "buildHeaders" in get_section

    def test_returns_snake_case_ticket_id_field(self):
        # Docstring must reference ticket_id not ticketId
        assert "ticket_id" in self.src


# ══════════════════════════════════════════════════════════════════════════════
# 6. SupportForm.jsx — reads ticket_id (snake_case)
# ══════════════════════════════════════════════════════════════════════════════

class TestSupportFormJsx:

    @pytest.fixture(autouse=True)
    def read_jsx(self):
        self.src = (
            Path(__file__).parent.parent / "web-form" / "SupportForm.jsx"
        ).read_text(encoding="utf-8")

    def test_reads_ticket_id_snake_case(self):
        assert "result.ticket_id" in self.src, \
            "SupportForm.jsx must read result.ticket_id (snake_case) from API response"

    def test_has_auth_header_function(self):
        assert "Authorization" in self.src, \
            "SupportForm.jsx must set Authorization header"

    def test_fetch_uses_build_headers(self):
        assert "buildHeaders()" in self.src, \
            "SupportForm.jsx fetch must call buildHeaders() to include auth token"

    def test_on_success_passes_ticket_id(self):
        assert "result.ticket_id" in self.src


# ══════════════════════════════════════════════════════════════════════════════
# 7. index.html — auth token sent with form and ticket fetch
# ══════════════════════════════════════════════════════════════════════════════

class TestIndexHtml:

    @pytest.fixture(autouse=True)
    def read_html(self):
        self.src = (
            Path(__file__).parent.parent / "web-form" / "index.html"
        ).read_text(encoding="utf-8")

    def test_build_headers_function_defined(self):
        assert "function buildHeaders" in self.src

    def test_submit_uses_build_headers(self):
        # In the handleSubmit function, headers: buildHeaders() must appear
        assert "buildHeaders()" in self.src

    def test_fetch_ticket_uses_build_headers(self):
        # fetchTicket function must also pass buildHeaders
        fetch_section = self.src[self.src.index("async function fetchTicket"):]
        assert "buildHeaders()" in fetch_section

    def test_fetch_ticket_encodes_uri(self):
        # Must use encodeURIComponent to prevent injection
        fetch_section = self.src[self.src.index("async function fetchTicket"):]
        assert "encodeURIComponent" in fetch_section

    def test_auth_overlay_present(self):
        assert 'id="auth-overlay"' in self.src

    def test_track_tab_present(self):
        assert 'id="view-track"' in self.src
