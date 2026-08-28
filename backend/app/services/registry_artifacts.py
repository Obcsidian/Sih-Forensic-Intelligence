"""Parses Windows registry hives (SOFTWARE/SYSTEM/NTUSER.DAT) extracted from
an E01/raw disk image into RegistryArtifact rows.

Uses regipy's plugin framework -- the same real hive-parsing Autopsy's
"Extracted Content" tree is built on -- instead of leaving hive files as
opaque EvidenceKind.other files with no interpretation. Every plugin's
entries dict/list shape was confirmed by installing regipy and inspecting
regipy/plugins/software/*.py and regipy/plugins/ntuser/*.py directly, since
those shapes aren't part of the library's public documentation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.models.registry_artifact import RegistryArtifactKind

# Maps the hive's on-disk filename (as found inside a Windows install) to
# regipy's own hive_type string (regipy.hive_types.*_HIVE_TYPE), passed
# explicitly to RegistryHive() so plugin compatibility matching doesn't
# depend on regipy successfully auto-detecting the hive's internal root key
# name -- a copy pulled off a disk image is exactly the case where that
# auto-detection is most likely to be unreliable.
REGISTRY_HIVE_FILENAMES = {"SOFTWARE": "software", "SYSTEM": "system", "NTUSER.DAT": "ntuser"}

_available: bool | None = None


def is_available() -> bool:
    global _available
    if _available is None:
        try:
            import regipy  # noqa: F401
        except ImportError:
            _available = False
        else:
            _available = True
    return _available


def identify_hive(name: str) -> str | None:
    """Returns the canonical hive filename (e.g. "SOFTWARE") if `name` is a
    known registry hive, matched case-insensitively -- the same convention
    KNOWN_ARTIFACT_FILENAMES uses in e01_ingestion.py."""
    upper = name.upper()
    return upper if upper in REGISTRY_HIVE_FILENAMES else None


@dataclass
class ParsedArtifact:
    kind: RegistryArtifactKind
    key_path: str
    name: str
    value: str
    raw: dict
    timestamp: datetime | None = None


def _coerce_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def _flatten_installed_programs(entries: list[dict], kind: RegistryArtifactKind) -> list[ParsedArtifact]:
    """InstalledProgramsSoftwarePlugin/InstalledProgramsNTUserPlugin: a list
    of dicts, each {"service_name", "timestamp", "registry_path", **extra
    registry values like DisplayName/DisplayVersion/Publisher}."""
    out = []
    for entry in entries:
        name = entry.get("DisplayName") or entry.get("service_name") or "(unnamed)"
        value = entry.get("DisplayVersion") or entry.get("Publisher") or ""
        out.append(
            ParsedArtifact(
                kind=kind,
                key_path=str(entry.get("registry_path", "")),
                name=str(name),
                value=str(value),
                raw=entry,
                timestamp=_coerce_datetime(entry.get("timestamp")),
            )
        )
    return out


def _flatten_persistence(entries: dict, kind: RegistryArtifactKind) -> list[ParsedArtifact]:
    """SoftwarePersistencePlugin/NTUserPersistencePlugin: a dict keyed by
    registry key path, each {"timestamp", "values": [Value(name, value, ...)]}."""
    out = []
    for key_path, info in entries.items():
        ts = _coerce_datetime(info.get("timestamp"))
        for v in info.get("values", []):
            v_name = v.get("name") if isinstance(v, dict) else getattr(v, "name", None)
            v_value = v.get("value") if isinstance(v, dict) else getattr(v, "value", None)
            out.append(
                ParsedArtifact(
                    kind=kind,
                    key_path=key_path,
                    name=str(v_name or ""),
                    value="" if v_value is None else str(v_value),
                    raw={"name": v_name, "value": v_value},
                    timestamp=ts,
                )
            )
    return out


def _flatten_winver(entries: dict) -> list[ParsedArtifact]:
    """WinVersionPlugin: a dict keyed by the OS-version key path, whose value
    is a flat dict of field name -> value (ProductName, CurrentVersion,
    RegisteredOwner, InstallDate, ...) plus a "last_write" timestamp."""
    out = []
    for key_path, fields in entries.items():
        last_write = _coerce_datetime(fields.get("last_write"))
        for field_name, field_value in fields.items():
            if field_name == "last_write":
                continue
            out.append(
                ParsedArtifact(
                    kind=RegistryArtifactKind.os_info,
                    key_path=key_path,
                    name=field_name,
                    value=str(field_value),
                    raw={field_name: field_value},
                    timestamp=last_write,
                )
            )
    return out


def _flatten_recent_docs(entries: list[dict]) -> list[ParsedArtifact]:
    """RecentDocsPlugin: a list of {"key_path", "last_write", "extension",
    "documents": [{"index", "name"}, ...]} -- one record per document."""
    out = []
    for entry in entries:
        ts = _coerce_datetime(entry.get("last_write"))
        for doc in entry.get("documents", []):
            out.append(
                ParsedArtifact(
                    kind=RegistryArtifactKind.recent_document,
                    key_path=str(entry.get("key_path", "")),
                    name=str(doc.get("name", "")),
                    value=entry.get("extension") or "",
                    raw={**doc, "extension": entry.get("extension")},
                    timestamp=ts,
                )
            )
    return out


def _flatten_network_list(entries: list[dict]) -> list[ParsedArtifact]:
    """NetworkListPlugin: a list mixing "profile" and "signature" typed
    dicts, keyed loosely (profile_name/description/dns_suffix/...)."""
    out = []
    for entry in entries:
        name = entry.get("profile_name") or entry.get("description") or entry.get("profile_guid") or entry.get("type") or "network"
        value = entry.get("description") or entry.get("dns_suffix") or ""
        ts = _coerce_datetime(entry.get("date_last_connected") or entry.get("date_created") or entry.get("last_write"))
        out.append(
            ParsedArtifact(
                kind=RegistryArtifactKind.network_connection,
                key_path=str(entry.get("key_path", "")),
                name=str(name),
                value=str(value),
                raw=entry,
                timestamp=ts,
            )
        )
    return out


def parse_hive(hive_path: Path, hive_name: str) -> list[ParsedArtifact]:
    """Best-effort parse of one extracted hive file. Each plugin run is
    isolated in its own try/except so one plugin choking on a damaged or
    atypical hive doesn't lose the others' results."""
    from regipy.registry import RegistryHive

    regipy_hive_type = REGISTRY_HIVE_FILENAMES.get(hive_name)
    if regipy_hive_type is None:
        return []

    hive = RegistryHive(str(hive_path), hive_type=regipy_hive_type)
    results: list[ParsedArtifact] = []

    def _run(plugin_cls, flatten) -> None:
        try:
            plugin = plugin_cls(hive, as_json=False)
            plugin.run()
            if plugin.entries:
                results.extend(flatten(plugin.entries))
        except Exception:
            pass

    if hive_name == "SOFTWARE":
        from regipy.plugins.software.installed_programs import InstalledProgramsSoftwarePlugin
        from regipy.plugins.software.networklist import NetworkListPlugin
        from regipy.plugins.software.persistence import SoftwarePersistencePlugin
        from regipy.plugins.software.winver import WinVersionPlugin

        _run(InstalledProgramsSoftwarePlugin, lambda e: _flatten_installed_programs(e, RegistryArtifactKind.installed_program))
        _run(SoftwarePersistencePlugin, lambda e: _flatten_persistence(e, RegistryArtifactKind.autorun_entry))
        _run(WinVersionPlugin, _flatten_winver)
        _run(NetworkListPlugin, _flatten_network_list)
    elif hive_name == "NTUSER.DAT":
        from regipy.plugins.ntuser.installed_programs_ntuser import InstalledProgramsNTUserPlugin
        from regipy.plugins.ntuser.persistence import NTUserPersistencePlugin
        from regipy.plugins.ntuser.recentdocs import RecentDocsPlugin

        _run(InstalledProgramsNTUserPlugin, lambda e: _flatten_installed_programs(e, RegistryArtifactKind.installed_program))
        _run(NTUserPersistencePlugin, lambda e: _flatten_persistence(e, RegistryArtifactKind.autorun_entry))
        _run(RecentDocsPlugin, _flatten_recent_docs)
    # SYSTEM hive: extracted and recognized, but no plugin wired up yet.

    return results
