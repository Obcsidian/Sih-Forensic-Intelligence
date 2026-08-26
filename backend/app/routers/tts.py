from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.models.user import User
from app.schemas.reports import TTSRequest
from app.security import require_any_role
from app.services import tts

router = APIRouter(prefix="/tts", tags=["tts"])


@router.post("")
def synthesize_speech(
    body: TTSRequest,
    _user: Annotated[User, Depends(require_any_role)],
) -> FileResponse:
    if not tts.is_available():
        raise HTTPException(status_code=503, detail="Text-to-speech dependencies are not installed (pyttsx3)")

    try:
        audio_path = tts.synthesize(body.text)
    except tts.ModelUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return FileResponse(str(audio_path), media_type="audio/wav", filename=audio_path.name)
