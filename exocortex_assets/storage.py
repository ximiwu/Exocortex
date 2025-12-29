from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Iterable

from .constants import ASSETS_ROOT
from .fs_utils import safe_rmtree
from .models import BlockData, GroupRecord


logger = logging.getLogger(__name__)


def get_asset_dir(asset_name: str) -> Path:
    """Return the on-disk directory for an asset (not validated)."""
    return ASSETS_ROOT / asset_name


def get_asset_config_path(asset_name: str) -> Path:
    """Return the path to the per-asset UI config JSON (not validated)."""
    return get_asset_dir(asset_name) / "config.json"


def load_asset_config(asset_name: str) -> dict[str, object]:
    """
    Load per-asset UI config. Returns empty dict if missing/invalid.
    """
    path = get_asset_config_path(asset_name)
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Failed to load asset config for '%s': %s", asset_name, exc)
        return {}
    if isinstance(raw, dict):
        return raw
    return {}


def save_asset_config(asset_name: str, data: dict[str, object]) -> Path:
    """
    Persist per-asset UI config using an atomic replace.
    """
    path = get_asset_config_path(asset_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    serialized = json.dumps(data, ensure_ascii=False, indent=2)
    tmp_path.write_text(serialized, encoding="utf-8")
    tmp_path.replace(path)
    return path


def get_group_data_dir(asset_name: str) -> Path:
    """Return the path where group data is stored for an asset."""
    return ASSETS_ROOT / asset_name / "group_data"


def get_group_record_path(asset_name: str, group_idx: int) -> Path:
    """Return the JSON path for a specific group record."""
    return get_group_data_dir(asset_name) / str(group_idx) / "group.json"


def load_group_records(asset_name: str) -> list[GroupRecord]:
    """Load all group records for an asset."""
    base_dir = get_group_data_dir(asset_name)
    if not base_dir.is_dir():
        return []
    records: list[GroupRecord] = []
    for entry in base_dir.iterdir():
        if not entry.is_dir():
            continue
        try:
            group_idx = int(entry.name)
        except Exception:  # pragma: no cover - defensive parsing
            continue
        data_path = entry / "group.json"
        if not data_path.is_file():
            continue
        try:
            payload = json.loads(data_path.read_text(encoding="utf-8"))
            records.append(GroupRecord.from_dict(payload, default_idx=group_idx))
        except Exception as exc:  # pragma: no cover - defensive parsing
            logger.warning(
                "Skipping invalid group data for '%s' at %s: %s", asset_name, data_path, exc
            )
    return sorted(records, key=lambda record: record.group_idx)


def next_group_idx(asset_name: str, existing: Iterable[GroupRecord] | None = None) -> int:
    """Return the next available group index for an asset."""
    records = list(existing) if existing is not None else load_group_records(asset_name)
    max_idx = max((record.group_idx for record in records), default=0)
    return max_idx + 1


def save_group_record(asset_name: str, record: GroupRecord) -> Path:
    """
    Persist a group record for an asset using an atomic replace.
    """
    path = get_group_record_path(asset_name, record.group_idx)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    serialized = json.dumps(record.to_dict(), ensure_ascii=False, indent=2)
    tmp_path.write_text(serialized, encoding="utf-8")
    tmp_path.replace(path)
    return path


def create_group_record(asset_name: str, block_ids: list[int], group_idx: int | None = None) -> GroupRecord:
    """
    Create and persist a group record for the given block ids.
    """
    if not block_ids:
        raise ValueError("No block ids provided to group.")
    records = load_group_records(asset_name) if group_idx is None else None
    resolved_idx = group_idx if group_idx is not None else next_group_idx(asset_name, records)
    record = GroupRecord(group_idx=resolved_idx, block_ids=list(dict.fromkeys(block_ids)))
    save_group_record(asset_name, record)
    return record


def delete_group_record(asset_name: str, group_idx: int) -> None:
    """Delete a group record directory (and all contents) if it exists."""
    path = get_group_record_path(asset_name, group_idx)
    try:
        parent = path.parent
        if parent.is_dir():
            safe_rmtree(parent)
        elif path.is_file():
            path.unlink()
    except Exception as exc:  # pragma: no cover - defensive cleanup
        logger.warning(
            "Failed to delete group record for '%s' (group %s): %s", asset_name, group_idx, exc
        )


def load_group_record(asset_name: str, group_idx: int) -> GroupRecord:
    """Load a single group record or raise if missing/invalid."""
    path = get_group_record_path(asset_name, group_idx)
    if not path.is_file():
        raise FileNotFoundError(
            f"Group record not found for asset '{asset_name}', group {group_idx}: {path}"
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return GroupRecord.from_dict(payload, default_idx=group_idx)
    except Exception as exc:
        raise ValueError(f"Invalid group record at {path}") from exc


def get_asset_pdf_path(asset_name: str) -> Path:
    """Return the path to the stored raw PDF for an asset (not validated)."""
    return ASSETS_ROOT / asset_name / "raw.pdf"


def get_block_data_path(asset_name: str) -> Path:
    """Return the path to the block data JSON for an asset (not validated)."""
    return ASSETS_ROOT / asset_name / "block_data" / "blocks.json"


def list_assets() -> list[str]:
    """List existing asset names (directories under ASSETS_ROOT)."""
    if not ASSETS_ROOT.is_dir():
        return []
    assets: list[str] = []
    for raw_pdf in ASSETS_ROOT.rglob("raw.pdf"):
        if not raw_pdf.is_file():
            continue
        try:
            relative_dir = raw_pdf.parent.relative_to(ASSETS_ROOT)
        except Exception:  # pragma: no cover - defensive
            continue
        assets.append(relative_dir.as_posix())
    return sorted(dict.fromkeys(assets))


def load_block_data(asset_name: str) -> BlockData:
    """
    Load block data for an asset. Returns empty data if file is missing or invalid.
    """
    path = get_block_data_path(asset_name)
    if not path.is_file():
        return BlockData.empty()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return BlockData.from_dict(raw)
    except Exception as exc:  # pragma: no cover - defensive path
        logger.warning("Failed to load block data for '%s': %s", asset_name, exc)
        return BlockData.empty()


def save_block_data(asset_name: str, data: BlockData) -> Path:
    """
    Persist block data for an asset using an atomic replace.
    """
    path = get_block_data_path(asset_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    serialized = json.dumps(data.to_dict(), ensure_ascii=False, indent=2)
    tmp_path.write_text(serialized, encoding="utf-8")
    tmp_path.replace(path)
    return path

