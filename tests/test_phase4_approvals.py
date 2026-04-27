import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from pathlib import Path
import sys
import os

# Adjust path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.contracts import validate_action_intent, ContractValidationResult
from agents.preflight_validator import PreflightApprovalEngine, PreflightApprovalError
from agents.google_operator import GmailOperator, CalendarOperator
from agents.orchestrator import Orchestrator
from agents.logic import event_bus

# --- Fixtures ---

@pytest.fixture(autouse=True)
def reset_system_state():
    """Reset event bus and any global state before each test."""
    if hasattr(event_bus, "_buffer"):
        event_bus._buffer.clear()
    yield

@pytest.fixture
def mock_event_bus():
    """Mock the event bus emit_event function."""
    with patch('agents.logic.event_bus.emit_event') as mock_emit:
        yield mock_emit

@pytest.fixture
def approval_engine(tmp_path):
    """Provide a fresh, isolated PreflightApprovalEngine instance."""
    store_path = tmp_path / "preflight_approvals.json"
    draft_store_path = tmp_path / "preflight_drafts.json"
    return PreflightApprovalEngine(store_path=store_path, draft_store_path=draft_store_path)

@pytest.fixture
def valid_action_intent():
    return {
        "action": "test_action",
        "agent_id": "AGT-001",
        "parameters": {"param1": "value1", "param2": 123},
        "trace_id": "test_trace_123",
        "requires_approval": True,
        "status": "pending"
    }

# --- Test agents.contracts.py ---

def test_validate_action_intent_valid(valid_action_intent):
    result = validate_action_intent(valid_action_intent)
    assert result.ok is True

def test_validate_action_intent_missing_field(valid_action_intent):
    del valid_action_intent["action"]
    result = validate_action_intent(valid_action_intent)
    assert result.ok is False
    assert "missing_required:$.action" in result.reason

def test_validate_action_intent_invalid_type(valid_action_intent):
    valid_action_intent["parameters"] = "not_an_object"
    result = validate_action_intent(valid_action_intent)
    assert result.ok is False
    assert "type_error:$.parameters" in result.reason

def test_validate_action_intent_incorrect_requires_approval(valid_action_intent):
    valid_action_intent["requires_approval"] = False
    result = validate_action_intent(valid_action_intent)
    assert result.ok is False
    assert "const_error:$.requires_approval" in result.reason

def test_validate_action_intent_invalid_status(valid_action_intent):
    valid_action_intent["status"] = "invalid_status"
    result = validate_action_intent(valid_action_intent)
    assert result.ok is False
    assert "enum_error:$.status" in result.reason

# --- Test agents.firewall.py (PreflightApprovalEngine) ---

def test_create_or_get_request(approval_engine, valid_action_intent):
    request = approval_engine.create_or_get_request(valid_action_intent)
    assert request is not None
    assert request["status"] == "pending"
    assert request["action"] == valid_action_intent["action"]
    assert request["agent_id"] == valid_action_intent["agent_id"]
    assert request["trace_id"] == valid_action_intent["trace_id"]
    assert request["payload"] == valid_action_intent["parameters"]
    assert "original_action_intent" in request
    assert approval_engine.list_requests("pending")[0]["request_id"] == request["request_id"]

def test_create_or_get_request_same_pending(approval_engine, valid_action_intent):
    first_request = approval_engine.create_or_get_request(valid_action_intent)
    second_request = approval_engine.create_or_get_request(valid_action_intent)
    assert first_request["request_id"] == second_request["request_id"]
    assert len(approval_engine.list_requests()) == 1

def test_decide_request_approve(approval_engine, valid_action_intent):
    request = approval_engine.create_or_get_request(valid_action_intent)
    decided_request = approval_engine.decide_request(request["request_id"], "approve")
    assert decided_request["status"] == "approved"
    assert approval_engine.get_request(request["request_id"])["status"] == "approved"

def test_decide_request_reject(approval_engine, valid_action_intent):
    request = approval_engine.create_or_get_request(valid_action_intent)
    decided_request = approval_engine.decide_request(request["request_id"], "reject")
    assert decided_request["status"] == "rejected"
    assert approval_engine.get_request(request["request_id"])["status"] == "rejected"

def test_ensure_approved_no_request(approval_engine):
    with pytest.raises(PreflightApprovalError) as excinfo:
        approval_engine.ensure_approved(
            action="non_existent_action",
            parameters={},
            agent_id="AGT-XYZ",
            trace_id="no_trace"
        )
    assert "external_action_requires_approval" in excinfo.value.reason

def test_ensure_approved_pending_request(approval_engine, valid_action_intent):
    approval_engine.create_or_get_request(valid_action_intent)
    with pytest.raises(PreflightApprovalError) as excinfo:
        approval_engine.ensure_approved(
            action=valid_action_intent["action"],
            parameters=valid_action_intent["parameters"],
            agent_id=valid_action_intent["agent_id"],
            trace_id=valid_action_intent["trace_id"]
        )
    assert "external_action_requires_approval" in excinfo.value.reason

def test_ensure_approved_rejected_request(approval_engine, valid_action_intent):
    request = approval_engine.create_or_get_request(valid_action_intent)
    approval_engine.decide_request(request["request_id"], "reject")
    with pytest.raises(PreflightApprovalError) as excinfo:
        approval_engine.ensure_approved(
            action=valid_action_intent["action"],
            parameters=valid_action_intent["parameters"],
            agent_id=valid_action_intent["agent_id"],
            trace_id=valid_action_intent["trace_id"]
        )
    assert "external_action_rejected" in excinfo.value.reason

def test_ensure_approved_approved_matching_hash(approval_engine, valid_action_intent):
    request = approval_engine.create_or_get_request(valid_action_intent)
    approval_engine.decide_request(request["request_id"], "approve")
    
    approved_req = approval_engine.ensure_approved(
        action=valid_action_intent["action"],
        parameters=valid_action_intent["parameters"],
        agent_id=valid_action_intent["agent_id"],
        trace_id=valid_action_intent["trace_id"]
    )
    assert approved_req["status"] == "approved"
    assert approved_req["request_id"] == request["request_id"]

def test_ensure_approved_approved_mismatching_hash(approval_engine, valid_action_intent):
    request = approval_engine.create_or_get_request(valid_action_intent)
    approval_engine.decide_request(request["request_id"], "approve")
    
    mismatched_parameters = {"param1": "different_value"}
    with pytest.raises(PreflightApprovalError) as excinfo:
        approval_engine.ensure_approved(
            action=valid_action_intent["action"],
            parameters=mismatched_parameters,
            agent_id=valid_action_intent["agent_id"],
            trace_id=valid_action_intent["trace_id"]
        )
    assert "executing_payload_mismatch" in excinfo.value.reason

# --- Test agents.google_operator.py ---

@pytest.mark.asyncio
async def test_gmail_send_draft_for_review_approved(mock_event_bus, tmp_path):
    """Test GmailOperator by mocking the internal Preflight engine and Gmail API."""
    # Isolated engine for this test
    store_path = tmp_path / "gmail_test.json"
    engine = PreflightApprovalEngine(store_path=store_path)
    
    with patch('agents.google_operator.PreflightApprovalEngine', engine), \
         patch('agents.google_operator.GmailOperator.get_service') as mock_get_service:
        
        gmail_op = GmailOperator(agent_id="test_agent")
        
        # Pre-approve the intent
        action_intent = {
            "action": "gmail_send_review",
            "agent_id": "test_agent",
            "parameters": {
                "to": "dalepsaila@gmail.com",
                "subject": "RESPONSE TO EMAIL (Test Subject) DRAFT",
                "body": "Test body"
            },
            "trace_id": "trace_gmail_approved",
            "requires_approval": True,
            "status": "pending"
        }
        request = engine.create_or_get_request(action_intent)
        engine.decide_request(request["request_id"], "approve")

        # Mock Gmail API response
        mock_service = MagicMock()
        mock_get_service.return_value = mock_service
        mock_service.users().messages().send().execute.return_value = {"id": "msg123"}

        result = await gmail_op.send_draft_for_review("Test Subject", "Test body", trace_id="trace_gmail_approved")
        
        assert "Draft review sent" in result
        mock_event_bus.assert_any_call("ACTION_INTENT_CREATED", "trace_gmail_approved", agent_id="test_agent", scenario="preflight", metadata={"action": "gmail_send_review", "intent_payload": action_intent["parameters"]})
        mock_event_bus.assert_any_call("ACTION_EXECUTED", "trace_gmail_approved", agent_id="test_agent", scenario="preflight", metadata={"action": "gmail_send_review", "target": "dalepsaila@gmail.com", "request_id": request["request_id"], "message_id": "msg123"})

@pytest.mark.asyncio
async def test_calendar_create_event_approved(mock_event_bus, tmp_path):
    """Test CalendarOperator by mocking the internal Preflight engine and Calendar API."""
    store_path = tmp_path / "calendar_test.json"
    engine = PreflightApprovalEngine(store_path=store_path)
    
    with patch('agents.google_operator.PreflightApprovalEngine', engine), \
         patch('agents.google_operator.CalendarOperator.get_service') as mock_get_service:
        
        calendar_op = CalendarOperator(agent_id="test_agent")
        
        # Pre-approve the intent
        action_intent = {
            "action": "calendar_create_event",
            "agent_id": "test_agent",
            "parameters": {
                "summary": "Test Event",
                "description": "Desc",
                "start_time": "2099-01-01T09:00:00Z",
                "end_time": "2099-01-01T10:00:00Z"
            },
            "trace_id": "trace_calendar_approved",
            "requires_approval": True,
            "status": "pending"
        }
        request = engine.create_or_get_request(action_intent)
        engine.decide_request(request["request_id"], "approve")

        # Mock Calendar API response
        mock_service = MagicMock()
        mock_get_service.return_value = mock_service
        mock_service.events().insert().execute.return_value = {"htmlLink": "http://event.link"}

        result = await calendar_op.create_event("Test Event", "2099-01-01T09:00:00Z", "2099-01-01T10:00:00Z", "Desc", trace_id="trace_calendar_approved")
        
        assert "Event created" in result
        mock_event_bus.assert_any_call("ACTION_EXECUTED", "trace_calendar_approved", agent_id="test_agent", scenario="preflight", metadata={"action": "calendar_create_event", "target": "primary", "request_id": request["request_id"], "event_link": "http://event.link"})

# --- Test agents.orchestrator.py (Morning Brief) ---

@pytest.fixture
def mock_orchestrator_llm_response():
    with patch('agents.orchestrator.CONTRACT_MODEL_MAP', {
        "morning_brief_v1": MagicMock()
    }) as mock_map:
        mock_brief = {
            "top_priorities": [
                "Finalize Q4 project timeline",
                "Prepare client presentation",
                "Review budget allocations"
            ],
            "risks": [
                "Delayed supplier delivery",
                "Resource allocation conflict"
            ],
            "schedule": [
                "09:00 Team standup",
                "11:00 Client meeting"
            ],
            "inputs": [
                "Latest emails",
                "Calendar events"
            ],
            "insight": "Early identification of scope gaps reduces downstream cost impact.",
            "first_action": "Review today's calendar and confirm priorities with team leads."
        }
        mock_map["morning_brief_v1"].invoke.return_value.content = json.dumps(mock_brief)
        yield mock_map["morning_brief_v1"]

@pytest.mark.asyncio
async def test_astream_chat_morning_brief(mock_orchestrator_llm_response, mock_event_bus):
    orchestrator = Orchestrator()
    
    # Mock data gathering to avoid real API calls
    from unittest.mock import AsyncMock
    orchestrator._gather_morning_brief_data = AsyncMock(return_value={
        "timestamp": "2026-04-16T10:00:00",
        "emails": [{"id": "e1", "snippet": "Hello"}],
        "calendar_events": [{"summary": "Meeting"}]
    })

    # Mock AGENTS to ensure Jenny is available for the test
    with patch.dict('agents.orchestrator.AGENTS', {
        "jenny": {
            "id": "AGT-009",
            "name": "Jenny",
            "title": "Communications Lead",
            "llm": MagicMock(),
            "triggers": ["morning brief"]
        }
    }):
        message = "morning brief"
        response_chunks = [chunk async for chunk in orchestrator.astream_chat(message)]

        assert any("[SYSTEM] Gathering data for Morning Brief..." in chunk for chunk in response_chunks)
        assert any("[JENNY] START" in chunk for chunk in response_chunks)
        assert any("Early identification" in chunk for chunk in response_chunks)
        assert any("[JENNY] END" in chunk for chunk in response_chunks)
        
        from unittest.mock import ANY
        mock_orchestrator_llm_response.invoke.assert_called_once()
        mock_event_bus.assert_any_call("ACTION_INTENT_CREATED", 
                                                ANY,
                                                agent_id="jenny", scenario="preflight", metadata={'action': 'morning_brief_v1', 'intent_payload': {
                                                    "top_priorities": [
                                                        "Finalize Q4 project timeline",
                                                        "Prepare client presentation",
                                                        "Review budget allocations"
                                                    ],
                                                    "risks": [
                                                        "Delayed supplier delivery",
                                                        "Resource allocation conflict"
                                                    ],
                                                    "schedule": [
                                                        "09:00 Team standup",
                                                        "11:00 Client meeting"
                                                    ],
                                                    "inputs": [
                                                        "Latest emails",
                                                        "Calendar events"
                                                    ],
                                                    "insight": "Early identification of scope gaps reduces downstream cost impact.",
                                                    "first_action": "Review today's calendar and confirm priorities with team leads."
                                                }})
