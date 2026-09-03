import asyncio
from unittest.mock import AsyncMock, patch

from .. import worker


def test_discover_and_submit_skips_tickets_that_already_have_a_job():
    open_tickets = [
        {"id": "t1", "subject": "Can't log in", "category": "technical", "ticket_number": "T-001"},
        {"id": "t2", "subject": "Refund please", "category": "billing", "ticket_number": "T-002"},
    ]
    existing_jobs = [{"input_reference": "t1"}]  # t1 already has a job

    with patch.object(worker, "synkra_os") as mock_pb, \
         patch.object(worker.discovery, "synkra_os", mock_pb):
        async def fake_list_records(collection, filter_expr="", per_page=100, sort=""):
            if collection == "support_tickets":
                return open_tickets
            if collection == "ai_jobs":
                return existing_jobs
            return []
        mock_pb.list_records = AsyncMock(side_effect=fake_list_records)
        mock_pb.submit_ai_job = AsyncMock(return_value={"job_id": "job_t2", "human_review_required": True})

        asyncio.run(worker.discover_and_submit())

        # Only t2 should have gotten a submitted job — t1 was already covered.
        assert mock_pb.submit_ai_job.call_count == 1
        call_kwargs = mock_pb.submit_ai_job.call_args.kwargs
        assert call_kwargs["input_reference"] == "t2"
        assert call_kwargs["action"] == "support.manage"  # billing category -> always escalate


def test_discover_and_submit_uses_email_manage_for_low_risk_ticket():
    open_tickets = [{"id": "t3", "subject": "How do I reset my password", "category": "technical", "ticket_number": "T-003"}]

    with patch.object(worker, "synkra_os") as mock_pb, \
         patch.object(worker.discovery, "synkra_os", mock_pb):
        async def fake_list_records(collection, filter_expr="", per_page=100, sort=""):
            if collection == "support_tickets":
                return open_tickets
            return []
        mock_pb.list_records = AsyncMock(side_effect=fake_list_records)
        mock_pb.submit_ai_job = AsyncMock(return_value={"job_id": "job_t3", "human_review_required": False})

        asyncio.run(worker.discover_and_submit())

        call_kwargs = mock_pb.submit_ai_job.call_args.kwargs
        assert call_kwargs["action"] == "email.manage"


def test_execute_job_self_escalates_when_drafting_is_not_wired():
    """Since draft_reply() always returns confidence=0.0 until a real LLM
    is wired, execute_job must ALWAYS self-escalate right now — never
    auto-send an unreviewed placeholder. This is the single most
    important safety property of the current, unwired state."""
    job = {"id": "job1", "input_reference": "t1", "ai_employee": "ai1"}
    ticket = {"id": "t1", "subject": "Can't log in", "category": "technical", "customer": "c1"}
    customer = {"id": "c1", "email": "customer@example.com", "name": "Jane"}

    with patch.object(worker, "synkra_os") as mock_pb, \
         patch.object(worker.knowledge, "synkra_os", mock_pb):
        async def fake_get_record(collection, record_id):
            return ticket if collection == "support_tickets" else customer
        mock_pb.get_record = AsyncMock(side_effect=fake_get_record)
        mock_pb.list_records = AsyncMock(return_value=[])  # no conversation history, no KB results
        mock_pb.send_email = AsyncMock()  # should NEVER be called in this test
        mock_pb.create_record = AsyncMock()
        mock_pb.report_job_result = AsyncMock()

        asyncio.run(worker.execute_job(job))

        mock_pb.send_email.assert_not_called()
        mock_pb.report_job_result.assert_called_once()
        call_args = mock_pb.report_job_result.call_args
        assert call_args.kwargs.get("status") == "escalated" or call_args.args[1] == "escalated"


def test_execute_job_auto_sends_when_confidence_clears_threshold():
    """Simulates a wired draft_reply() returning high confidence, to
    prove the auto-send path itself works correctly once drafting is
    real — separate from proving it correctly refuses to fire today."""
    job = {"id": "job2", "input_reference": "t2", "ai_employee": "ai1"}
    ticket = {"id": "t2", "subject": "How do I reset my password", "category": "technical", "customer": "c2"}
    customer = {"id": "c2", "email": "customer2@example.com", "name": "Bob"}

    async def fake_get_record(collection, record_id):
        return ticket if collection == "support_tickets" else customer

    with patch.object(worker, "synkra_os") as mock_pb, \
         patch.object(worker.knowledge, "synkra_os", mock_pb), \
         patch.object(worker, "draft_reply", new=AsyncMock(return_value=("Here's how to reset your password...", 0.95))):
        mock_pb.get_record = AsyncMock(side_effect=fake_get_record)
        mock_pb.list_records = AsyncMock(return_value=[])
        mock_pb.send_email = AsyncMock(return_value={"email_event_id": "evt1"})
        mock_pb.create_record = AsyncMock()
        mock_pb.report_job_result = AsyncMock()

        asyncio.run(worker.execute_job(job))

        mock_pb.send_email.assert_called_once()
        sent_kwargs = mock_pb.send_email.call_args.kwargs
        assert sent_kwargs["to"] == "customer2@example.com"
        mock_pb.create_record.assert_called_once()  # logged the sent reply as a conversation
        report_call = mock_pb.report_job_result.call_args
        assert report_call.kwargs.get("status") == "succeeded" or report_call.args[1] == "succeeded"
