from __future__ import annotations

from integrations.boards.models import (
    ActivityEventRef,
    AgentRef,
    ApprovalRef,
    BoardConnection,
    CompanyRef,
    CompanySnapshot,
    GoalRef,
    HeartbeatRunRef,
    IssueRef,
    ProjectRef,
    map_remote_issue_status,
    map_remote_run_status,
)


class TestBoardModels:
    def test_company_snapshot_keeps_normalized_refs_and_raw_payloads(self):
        snapshot = CompanySnapshot(
            company=CompanyRef(id="comp_1", name="Acme", slug="acme", raw={"id": "comp_1"}),
            issues=[
                IssueRef(
                    id="iss_1",
                    company_id="comp_1",
                    title="Investigate board sync",
                    status="in_progress",
                    project_id="proj_1",
                    goal_id="goal_1",
                    assignee_agent_id="agent_1",
                    raw={"remote": True},
                )
            ],
            projects=[ProjectRef(id="proj_1", company_id="comp_1", name="Hermes Board", raw={"p": 1})],
            goals=[GoalRef(id="goal_1", company_id="comp_1", name="Ship board MVP", raw={"g": 1})],
            agents=[AgentRef(id="agent_1", company_id="comp_1", name="Hermes", raw={"a": 1})],
            approvals=[ApprovalRef(id="appr_1", issue_id="iss_1", status="pending", raw={"ok": False})],
            heartbeat_runs=[HeartbeatRunRef(id="run_1", issue_id="iss_1", status="running", raw={"step": 3})],
            activity_events=[ActivityEventRef(id="evt_1", issue_id="iss_1", type="comment_added", raw={"msg": "yo"})],
            raw={"snapshot": True},
        )

        assert snapshot.company.slug == "acme"
        assert snapshot.issues[0].project_id == "proj_1"
        assert snapshot.approvals[0].raw == {"ok": False}
        assert snapshot.heartbeat_runs[0].raw == {"step": 3}
        assert snapshot.activity_events[0].type == "comment_added"
        assert snapshot.raw == {"snapshot": True}

    def test_board_connection_tracks_credentials_and_timestamps(self):
        connection = BoardConnection(
            id="conn_1",
            provider="paperclip",
            company_id="comp_1",
            company_slug="acme",
            company_name="Acme",
            auth_mode="agent_key",
            credential_ref="paperclip:default",
            is_active=True,
            provider_user_id="agent_1",
            provider_user_name="Hermes",
            created_at=1711970000.5,
            updated_at=1711971234.5,
            last_synced_at="2026-04-01T14:05:00Z",
            raw={"scope": "company"},
        )

        assert connection.provider == "paperclip"
        assert connection.credential_ref == "paperclip:default"
        assert connection.is_active is True
        assert connection.last_synced_at == "2026-04-01T14:05:00Z"
        assert connection.raw == {"scope": "company"}

    def test_issue_and_run_status_mapping_helpers(self):
        assert map_remote_issue_status("todo") == "pending"
        assert map_remote_issue_status("backlog") == "pending"
        assert map_remote_issue_status("in_progress") == "in_progress"
        assert map_remote_issue_status("IN REVIEW") == "in_progress"
        assert map_remote_issue_status("done") == "completed"
        assert map_remote_issue_status("canceled") == "cancelled"
        assert map_remote_issue_status(None) == "unknown"
        assert map_remote_issue_status("weird-custom-state") == "unknown"

        assert map_remote_run_status("queued") == "queued"
        assert map_remote_run_status("running") == "running"
        assert map_remote_run_status("success") == "completed"
        assert map_remote_run_status("failed") == "failed"
        assert map_remote_run_status("cancelled") == "cancelled"
        assert map_remote_run_status(None) == "unknown"
        assert map_remote_run_status("banana") == "unknown"
