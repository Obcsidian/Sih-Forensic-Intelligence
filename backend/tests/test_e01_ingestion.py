import pytest

from app.models.evidence_file import EvidenceKind
from app.services.e01_ingestion import KNOWN_ARTIFACT_FILENAMES, _classify, resolve_parser
from app.services.ingestion import CaseFolderParser


def test_classify_recognizes_media_extensions():
    assert _classify("photo.jpg") == EvidenceKind.photo
    assert _classify("clip.mp4") == EvidenceKind.video
    assert _classify("voice.m4a") == EvidenceKind.audio


def test_classify_recognizes_known_artifact_filenames():
    assert _classify("contacts2.db") == EvidenceKind.document
    assert _classify("mmssms.db") == EvidenceKind.document


def test_classify_returns_none_for_unrecognized_file():
    assert _classify("readme.txt") is None
    assert _classify("random.bin") is None


def test_known_artifact_filenames_are_lowercase_keys():
    for name in KNOWN_ARTIFACT_FILENAMES:
        assert name == name.lower()


def test_resolve_parser_returns_folder_parser_for_directory(tmp_path):
    assert isinstance(resolve_parser(tmp_path), CaseFolderParser)


def test_resolve_parser_raises_for_unrecognized_file(tmp_path):
    bogus = tmp_path / "notes.txt"
    bogus.write_text("hello")
    with pytest.raises(ValueError, match="neither a readable case-export folder"):
        resolve_parser(bogus)


def test_resolve_parser_e01_path(tmp_path):
    from app.services import e01_ingestion

    image = tmp_path / "case.E01"
    image.write_bytes(b"not a real EWF file")

    if e01_ingestion.is_available():
        parser = resolve_parser(image)
        assert isinstance(parser, e01_ingestion.E01Parser)
    else:
        with pytest.raises(ValueError, match="E01 support isn't installed"):
            resolve_parser(image)
