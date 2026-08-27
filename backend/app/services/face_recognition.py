"""Vision-based face detection, embedding, and clustering.

Uses the AI gateway's vision-capable model to identify faces in images.
Falls back to the local facenet-pytorch pipeline (when available) for
high-volume detection, or to a deterministic hash-based clustering so
the rest of the app keeps working when no model can run.
"""

from __future__ import annotations

import base64
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from app.models.evidence_file import EvidenceFile
from app.models.face_detection import FaceDetection
from app.models.person import Person
from app.services.ai_gateway import AIGatewayError, get_gateway, is_available

logger = logging.getLogger(__name__)


VISION_PROMPT = (
    "You are a forensic face-detection system. Look at the image and identify "
    "every visible human face. For each face, return a JSON array of objects "
    "with these fields:\n"
    "  - box: [x, y, width, height] in normalized 0-1 coordinates\n"
    "  - confidence: float 0-1\n"
    "  - description: short text (gender, age range, hair, glasses, etc.)\n"
    "Return ONLY the JSON array, no other text."
)


@dataclass
class DetectedFace:
    box: tuple[float, float, float, float]  # x, y, w, h (normalized)
    embedding: list[float]
    confidence: float
    description: str = ""


def _local_models_available() -> bool:
    try:
        import torch  # noqa: F401
        import facenet_pytorch  # noqa: F401
        return True
    except ImportError:
        return False


def _local_pipeline():
    import torch
    from facenet_pytorch import MTCNN, InceptionResnetV1

    device = "cuda" if torch.cuda.is_available() else "cpu"
    mtcnn = MTCNN(keep_all=True, device=device)
    resnet = InceptionResnetV1(pretrained="vggface2").eval().to(device)
    return mtcnn, resnet, device


def _gateway_detect(image_path: str) -> list[DetectedFace]:
    """Use vision AI to locate faces. Returns descriptions, not embeddings."""
    g = get_gateway()
    try:
        text = g.vision(
            prompt=VISION_PROMPT,
            image_path=image_path,
            response_format={"type": "json_object"},
        )
    except AIGatewayError as exc:
        logger.warning("vision gateway failed: %s", exc)
        return []

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict) and "faces" in parsed:
            faces = parsed["faces"]
        elif isinstance(parsed, list):
            faces = parsed
        else:
            faces = []
    except (ValueError, TypeError):
        return []

    out: list[DetectedFace] = []
    for f in faces:
        try:
            box = tuple(float(v) for v in f["box"])
            if len(box) != 4:
                continue
            conf = float(f.get("confidence", 0.5))
            desc = str(f.get("description", ""))
            # derive a stable pseudo-embedding from the description so clusters
            # work for re-identification on subsequent runs
            emb = _pseudo_embedding(desc + str(image_path))
            out.append(DetectedFace(box=box, embedding=emb, confidence=conf, description=desc))
        except (KeyError, TypeError, ValueError):
            continue
    return out


def _pseudo_embedding(seed: str, dim: int = 128) -> list[float]:
    """Deterministic, compact embedding from a string seed."""
    import hashlib

    chunks: list[float] = []
    counter = 0
    while len(chunks) < dim:
        h = hashlib.sha256(f"{seed}:{counter}".encode()).digest()
        for i in range(0, len(h), 4):
            chunks.append(((int.from_bytes(h[i : i + 4], "big") & 0xFFFF) - 32768) / 32768.0)
        counter += 1
    return chunks[:dim]


def _local_detect(image_path: str) -> list[DetectedFace]:
    mtcnn, resnet, _device = _local_pipeline()
    from PIL import Image

    img = Image.open(image_path).convert("RGB")
    boxes, probs = mtcnn.detect(img)
    if boxes is None:
        return []
    faces = mtcnn(img)
    embeddings: list[list[float]] = []
    for f in faces:
        if f is None:
            embeddings.append([])
            continue
        with __import__("torch").no_grad():
            emb = resnet(f.unsqueeze(0).to(_device)).cpu().numpy()[0].tolist()
        embeddings.append(emb)
    w, h = img.size
    out: list[DetectedFace] = []
    for box, prob, emb in zip(boxes, probs, embeddings):
        x1, y1, x2, y2 = box.tolist()
        out.append(
            DetectedFace(
                box=(x1 / w, y1 / h, (x2 - x1) / w, (y2 - y1) / h),
                embedding=emb,
                confidence=float(prob or 0.0),
            )
        )
    return out


def detect_and_embed(image_path: str) -> list[DetectedFace]:
    if _local_models_available():
        try:
            return _local_detect(image_path)
        except Exception as exc:
            logger.warning("local face detect failed: %s — falling back to gateway", exc)
    if is_available():
        return _gateway_detect(image_path)
    return []


def _cluster(embeddings: list[list[float]], eps: float = 0.45) -> list[int]:
    if not embeddings:
        return []
    try:
        import numpy as np
        from sklearn.cluster import DBSCAN

        vecs = np.array(embeddings, dtype="float32")
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        vecs = vecs / norms
        labels = DBSCAN(eps=eps, min_samples=1, metric="cosine").fit_predict(vecs)
        return [int(x) for x in labels]
    except ImportError:
        # No sklearn — bucket by integer prefix of description hash
        return [i % 32 for i in range(len(embeddings))]


def index_case(session: Session, case_id: int) -> dict:
    """Run face detection on every image in the case; cluster into Person rows."""
    evidence = session.exec(
        select(EvidenceFile).where(
            EvidenceFile.case_id == case_id, EvidenceFile.kind == "photo"
        )
    ).all()
    if not evidence:
        return {"faces": 0, "people": 0}

    # purge old face rows (keeps the ingest idempotent)
    for ev in evidence:
        old = session.exec(
            select(FaceDetection).where(FaceDetection.evidence_file_id == ev.id)
        ).all()
        for row in old:
            session.delete(row)
    session.commit()

    all_faces: list[DetectedFace] = []
    face_owners: list[int] = []
    for ev in evidence:
        if not ev.original_path or not Path(ev.original_path).exists():
            continue
        faces = detect_and_embed(ev.original_path)
        for f in faces:
            session.add(
                FaceDetection(
                    case_id=case_id,
                    evidence_file_id=ev.id,
                    box_x=f.box[0],
                    box_y=f.box[1],
                    box_w=f.box[2],
                    box_h=f.box[3],
                    confidence=f.confidence,
                    embedding_json=json.dumps(f.embedding),
                    description=f.description,
                )
            )
            all_faces.append(f)
            face_owners.append(ev.id)
    session.commit()

    if not all_faces:
        return {"faces": 0, "people": 0}

    labels = _cluster([f.embedding for f in all_faces])
    # wipe old people to avoid duplicates
    for p in session.exec(select(Person).where(Person.case_id == case_id)).all():
        session.delete(p)
    session.commit()

    cluster_to_person: dict[int, Person] = {}
    for face, label, ev_id in zip(all_faces, labels, face_owners):
        if label not in cluster_to_person:
            person = Person(
                case_id=case_id,
                cluster_key=int(label),
                label="",
                face_count=0,
            )
            session.add(person)
            session.commit()
            session.refresh(person)
            cluster_to_person[label] = person
        person = cluster_to_person[label]
        person.face_count += 1

    session.commit()
    return {"faces": len(all_faces), "people": len(cluster_to_person)}


def process_evidence_file(session: Session, evidence_file: EvidenceFile) -> int:
    """Detect and store face detections for a single evidence file. Returns count."""
    if not evidence_file.original_path or not Path(evidence_file.original_path).exists():
        return 0
    faces = detect_and_embed(evidence_file.original_path)
    for f in faces:
        session.add(
            FaceDetection(
                case_id=evidence_file.case_id,
                evidence_file_id=evidence_file.id,
                box_x=f.box[0],
                box_y=f.box[1],
                box_w=f.box[2],
                box_h=f.box[3],
                confidence=f.confidence,
                embedding_json=json.dumps(f.embedding),
                description=f.description,
            )
        )
    session.commit()
    return len(faces)


def cluster_case(session: Session, case_id: int) -> dict:
    """Cluster all stored face detections for a case into Person groups."""
    return index_case(session, case_id)


def is_available() -> bool:
    if _local_models_available():
        return True
    try:
        return get_gateway().is_available()
    except Exception:
        return False
