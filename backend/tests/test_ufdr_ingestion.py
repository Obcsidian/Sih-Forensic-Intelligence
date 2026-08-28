import zipfile

import pytest
from sqlmodel import select

from app.models.call import Call
from app.models.case import Case
from app.models.contact import Contact
from app.models.evidence_file import EvidenceFile
from app.models.message import Message
from app.services.e01_ingestion import resolve_parser
from app.services.ufdr_ingestion import CellebriteUFDRParser

REPORT_XML = """<?xml version="1.0" encoding="UTF-8"?>
<reports>
  <models>
    <model type="Contact" id="1">
      <field name="Name"><value>Alice</value></field>
      <field name="Phone"><value>+1111111111</value></field>
    </model>
    <model type="Call" id="2">
      <field name="Number"><value>+2222222222</value></field>
      <field name="Direction"><value>Outgoing</value></field>
      <field name="Duration"><value>90</value></field>
      <field name="TimeStamp"><value>2026-01-01 10:00:00</value></field>
    </model>
    <model type="SMS" id="3">
      <field name="From"><value>+1111111111</value></field>
      <field name="To"><value>device_owner</value></field>
      <field name="Body"><value>see you tonight</value></field>
      <field name="TimeStamp"><value>2026-01-01 09:00:00</value></field>
      <field name="Source"><value>sms</value></field>
    </model>
    <model type="Image" id="4">
      <field name="Filename"><value>photo1.jpg</value></field>
      <field name="Local Path"><value>Files/Image/photo1.jpg</value></field>
      <field name="TimeStamp"><value>2026-01-01 08:30:00</value></field>
    </model>
    <model type="Cookie" id="5">
      <field name="Name"><value>irrelevant</value></field>
    </model>
  </models>
</reports>
"""


def _make_ufdr(tmp_path):
    path = tmp_path / "case.ufdr"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("Reports/report.xml", REPORT_XML)
        zf.writestr("Files/Image/photo1.jpg", b"\xff\xd8\xff\xe0fakejpegbytes")
    return path


def test_resolve_parser_ufdr_extension(tmp_path):
    ufdr = _make_ufdr(tmp_path)
    assert isinstance(resolve_parser(ufdr), CellebriteUFDRParser)


def test_ingest_ufdr_populates_all_record_types(session, tmp_path):
    ufdr = _make_ufdr(tmp_path)
    case = Case(name="UFDR Test Case", source_path=str(ufdr))
    session.add(case)
    session.commit()
    session.refresh(case)

    summary = CellebriteUFDRParser().ingest(session, case, ufdr)

    assert summary.contacts == 1
    assert summary.calls == 1
    assert summary.messages == 1
    assert summary.photos == 1
    assert any("Cookie" in e for e in summary.errors)

    contacts = session.exec(select(Contact).where(Contact.case_id == case.id)).all()
    assert contacts[0].name == "Alice"
    assert contacts[0].phone_number == "+1111111111"

    calls = session.exec(select(Call).where(Call.case_id == case.id)).all()
    assert calls[0].direction.value == "outgoing"
    assert calls[0].duration_seconds == 90

    messages = session.exec(select(Message).where(Message.case_id == case.id)).all()
    assert messages[0].body == "see you tonight"

    evidence = session.exec(select(EvidenceFile).where(EvidenceFile.case_id == case.id)).all()
    assert len(evidence) == 1
    assert evidence[0].file_name == "photo1.jpg"
    from pathlib import Path

    assert Path(evidence[0].original_path).exists()


def test_ingest_ufdr_missing_report_xml(session, tmp_path):
    path = tmp_path / "empty.ufdr"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("readme.txt", "nothing here")

    case = Case(name="Empty UFDR", source_path=str(path))
    session.add(case)
    session.commit()
    session.refresh(case)

    summary = CellebriteUFDRParser().ingest(session, case, path)
    assert summary.contacts == 0
    assert any("no report.xml" in e for e in summary.errors)


def test_ingest_ufdr_bad_zip(session, tmp_path):
    path = tmp_path / "corrupt.ufdr"
    path.write_bytes(b"not a zip file at all")

    case = Case(name="Corrupt UFDR", source_path=str(path))
    session.add(case)
    session.commit()
    session.refresh(case)

    summary = CellebriteUFDRParser().ingest(session, case, path)
    assert any("not a valid UFDR/ZIP archive" in e for e in summary.errors)


def test_ingest_ufdr_parses_email_model_type(session, tmp_path):
    report_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <reports>
      <models>
        <model type="Email" id="1">
          <field name="From"><value>alice@example.com</value></field>
          <field name="To"><value>bob@example.com</value></field>
          <field name="Subject"><value>Quarterly report</value></field>
          <field name="Body"><value>Numbers are attached.</value></field>
          <field name="TimeStamp"><value>2026-02-01 12:00:00</value></field>
        </model>
      </models>
    </reports>
    """
    path = tmp_path / "email.ufdr"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("Reports/report.xml", report_xml)

    case = Case(name="Email UFDR Test", source_path=str(path))
    session.add(case)
    session.commit()
    session.refresh(case)

    summary = CellebriteUFDRParser().ingest(session, case, path)
    assert summary.messages == 1

    messages = session.exec(select(Message).where(Message.case_id == case.id)).all()
    assert messages[0].sender == "alice@example.com"
    assert messages[0].recipient == "bob@example.com"
    assert messages[0].body == "Subject: Quarterly report\n\nNumbers are attached."
