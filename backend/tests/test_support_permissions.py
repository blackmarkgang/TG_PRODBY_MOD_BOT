import pytest
from fastapi import HTTPException

from app.api.routes.support import require_assignee
from app.db.models import AdminUser, SupportTicket


def test_assigned_admin_can_work_with_ticket() -> None:
    admin = AdminUser(id=7, telegram_id=100, role="admin")
    ticket = SupportTicket(id=11, user_id=1, status="in_progress", assigned_admin_id=7)
    require_assignee(ticket, admin)


def test_other_admin_cannot_work_with_ticket() -> None:
    admin = AdminUser(id=8, telegram_id=101, role="admin")
    ticket = SupportTicket(id=11, user_id=1, status="in_progress", assigned_admin_id=7)
    with pytest.raises(HTTPException) as exc_info:
        require_assignee(ticket, admin)
    assert exc_info.value.status_code == 409


def test_closed_ticket_cannot_be_changed() -> None:
    admin = AdminUser(id=7, telegram_id=100, role="admin")
    ticket = SupportTicket(id=11, user_id=1, status="closed", assigned_admin_id=7)
    with pytest.raises(HTTPException) as exc_info:
        require_assignee(ticket, admin)
    assert exc_info.value.status_code == 409
