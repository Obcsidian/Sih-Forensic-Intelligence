from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.database import get_session
from app.models.face_detection import FaceDetection
from app.models.person import Person
from app.models.user import User
from app.security import require_any_role, require_investigator, require_reviewer_or_above
from app.services import audit_log, face_recognition

router = APIRouter(prefix="/cases/{case_id}", tags=["faces"])


class LabelPersonRequest(BaseModel):
    label: str


@router.get("/people", response_model=list[Person])
def list_people(
    case_id: int,
    session: Annotated[Session, Depends(get_session)],
    _user: Annotated[User, Depends(require_any_role)],
) -> list[Person]:
    return session.exec(select(Person).where(Person.case_id == case_id).order_by(Person.face_count.desc())).all()


@router.patch("/people/{person_id}", response_model=Person)
def label_person(
    case_id: int,
    person_id: int,
    body: LabelPersonRequest,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(require_reviewer_or_above)],
) -> Person:
    person = session.get(Person, person_id)
    if person is None or person.case_id != case_id:
        raise HTTPException(status_code=404, detail="Person not found")

    person.label = body.label
    session.add(person)
    session.commit()
    session.refresh(person)

    audit_log.append_entry(
        session, actor=user.username, action="person.label", case_id=case_id, payload={"person_id": person_id, "label": body.label}
    )
    return person


@router.get("/faces", response_model=list[FaceDetection])
def list_faces(
    case_id: int,
    session: Annotated[Session, Depends(get_session)],
    _user: Annotated[User, Depends(require_any_role)],
    person_id: int | None = None,
) -> list[FaceDetection]:
    query = select(FaceDetection).where(FaceDetection.case_id == case_id)
    if person_id is not None:
        query = query.where(FaceDetection.person_id == person_id)
    return session.exec(query).all()


@router.post("/faces/recluster")
def recluster_faces(
    case_id: int,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(require_investigator)],
) -> dict:
    if not face_recognition.is_available():
        raise HTTPException(status_code=503, detail="Face recognition model dependencies are not installed")

    people_found = face_recognition.cluster_case(session, case_id)
    audit_log.append_entry(
        session, actor=user.username, action="face.recluster", case_id=case_id, payload={"people_found": people_found}
    )
    return {"people_found": people_found}
