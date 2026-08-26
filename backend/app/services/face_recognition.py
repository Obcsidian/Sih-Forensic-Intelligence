"""Face detection, embedding and clustering.

Pipeline shape matches the README's InsightFace + FAISS/HDBSCAN design
(detect -> embed -> cluster), but uses facenet-pytorch (MTCNN + InceptionResnetV1)
for detection/embedding and scikit-learn for clustering, since both install
cleanly on Windows without a C/C++ build toolchain. Swap `_get_models()` for
an InsightFace loader to move to the README's original stack.
"""

import json
from dataclasses import dataclass
from functools import lru_cache

from sqlmodel import Session, select

from app.models.evidence_file import EvidenceFile
from app.models.face_detection import FaceDetection
from app.models.person import Person


class ModelUnavailableError(RuntimeError):
    """Raised when the optional ML dependencies for this service aren't installed."""


@lru_cache
def _get_models():
    try:
        import torch
        from facenet_pytorch import MTCNN, InceptionResnetV1
    except ImportError as exc:
        raise ModelUnavailableError(
            "Face recognition requires 'torch' and 'facenet-pytorch' — "
            "install backend/requirements.txt to enable this feature."
        ) from exc

    device = "cuda" if torch.cuda.is_available() else "cpu"
    mtcnn = MTCNN(keep_all=True, device=device)
    resnet = InceptionResnetV1(pretrained="vggface2").eval().to(device)
    return mtcnn, resnet, device


def is_available() -> bool:
    try:
        _get_models()
        return True
    except ModelUnavailableError:
        return False


@dataclass
class DetectedFace:
    box: tuple[float, float, float, float]  # x, y, w, h
    embedding: list[float]
    confidence: float


def detect_and_embed(image_path: str) -> list[DetectedFace]:
    from PIL import Image

    mtcnn, resnet, device = _get_models()

    import torch

    image = Image.open(image_path).convert("RGB")
    boxes, probs = mtcnn.detect(image)
    if boxes is None:
        return []

    faces = mtcnn.extract(image, boxes, save_path=None)
    if faces is None:
        return []

    with torch.no_grad():
        embeddings = resnet(faces.to(device)).cpu().numpy()

    results = []
    for box, prob, embedding in zip(boxes, probs, embeddings, strict=True):
        x1, y1, x2, y2 = box
        results.append(
            DetectedFace(
                box=(float(x1), float(y1), float(x2 - x1), float(y2 - y1)),
                embedding=embedding.tolist(),
                confidence=float(prob) if prob is not None else 0.0,
            )
        )
    return results


def process_evidence_file(session: Session, evidence_file: EvidenceFile) -> int:
    """Detect faces in one photo and store them as unclustered FaceDetection rows."""
    faces = detect_and_embed(evidence_file.original_path)
    for face in faces:
        session.add(
            FaceDetection(
                case_id=evidence_file.case_id,
                evidence_file_id=evidence_file.id,
                box_x=face.box[0],
                box_y=face.box[1],
                box_w=face.box[2],
                box_h=face.box[3],
                embedding_json=json.dumps(face.embedding),
                detection_confidence=face.confidence,
            )
        )
    session.commit()
    return len(faces)


def cluster_case(session: Session, case_id: int, min_cluster_size: int = 2) -> int:
    """Cluster every FaceDetection in a case into Person rows. Returns the number of people found."""
    import numpy as np

    try:
        from sklearn.cluster import HDBSCAN as _HDBSCAN

        clusterer = _HDBSCAN(min_cluster_size=min_cluster_size, metric="euclidean")
    except ImportError:
        from sklearn.cluster import DBSCAN

        clusterer = DBSCAN(eps=0.9, min_samples=min_cluster_size, metric="euclidean")

    detections = session.exec(select(FaceDetection).where(FaceDetection.case_id == case_id)).all()
    if not detections:
        return 0

    embeddings = np.array([json.loads(d.embedding_json) for d in detections])
    labels = clusterer.fit_predict(embeddings)

    # Wipe previous clustering for this case so re-running is idempotent.
    for existing in session.exec(select(Person).where(Person.case_id == case_id)).all():
        session.delete(existing)
    session.commit()

    people_by_label: dict[int, Person] = {}
    for detection, label in zip(detections, labels, strict=True):
        detection.person_id = None
        if label == -1:
            session.add(detection)
            continue

        person = people_by_label.get(int(label))
        if person is None:
            person = Person(case_id=case_id, cluster_key=int(label), face_count=0)
            session.add(person)
            session.flush()
            people_by_label[int(label)] = person

        detection.person_id = person.id
        person.face_count += 1
        if person.representative_face_id is None:
            person.representative_face_id = detection.id
        session.add(detection)
        session.add(person)

    session.commit()
    return len(people_by_label)
