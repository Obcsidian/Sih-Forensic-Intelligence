from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.database import get_session
from app.models.call import Call
from app.models.contact import Contact
from app.models.message import Message
from app.models.user import User
from app.security import require_any_role

router = APIRouter(prefix="/cases/{case_id}", tags=["communications"])


@router.get("/contacts", response_model=list[Contact])
def list_contacts(
    case_id: int,
    session: Annotated[Session, Depends(get_session)],
    _user: Annotated[User, Depends(require_any_role)],
) -> list[Contact]:
    return session.exec(select(Contact).where(Contact.case_id == case_id)).all()


@router.get("/calls", response_model=list[Call])
def list_calls(
    case_id: int,
    session: Annotated[Session, Depends(get_session)],
    _user: Annotated[User, Depends(require_any_role)],
) -> list[Call]:
    return session.exec(select(Call).where(Call.case_id == case_id).order_by(Call.timestamp.asc())).all()


@router.get("/messages", response_model=list[Message])
def list_messages(
    case_id: int,
    session: Annotated[Session, Depends(get_session)],
    _user: Annotated[User, Depends(require_any_role)],
) -> list[Message]:
    return session.exec(select(Message).where(Message.case_id == case_id).order_by(Message.timestamp.asc())).all()
