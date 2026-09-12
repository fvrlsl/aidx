from sqlalchemy.orm import Session

from app.models import AuditLog


def log(db: Session, operator: str, action: str, target_type: str, target_id: int | None, before=None, after=None) -> None:
    db.add(
        AuditLog(operator=operator, action=action, target_type=target_type, target_id=target_id, before=before, after=after)
    )
