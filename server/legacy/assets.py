from __future__ import annotations

from pathlib import Path

from assets_manager import (
    create_group_record as _create_group_record,
    delete_group_record as _delete_group_record,
    get_asset_dir as _get_asset_dir,
    get_asset_pdf_path as _get_asset_pdf_path,
    init_tutor as _init_tutor,
    list_assets as _list_assets,
    load_asset_config as _load_asset_config,
    load_block_data as _load_block_data,
    load_group_records as _load_group_records,
    save_asset_config as _save_asset_config,
    save_block_data as _save_block_data,
)
from exocortex_core.contracts import BlockData, BlockRecord, BlockRect, GroupRecord


def get_asset_dir(asset_name: str) -> Path:
    return _get_asset_dir(asset_name)


def get_asset_pdf_path(asset_name: str) -> Path:
    return _get_asset_pdf_path(asset_name)


def load_asset_config(asset_name: str) -> dict[str, object]:
    return _load_asset_config(asset_name)


def save_asset_config(asset_name: str, data: dict[str, object]) -> Path:
    return _save_asset_config(asset_name, data)


def load_block_data(asset_name: str) -> BlockData:
    return _load_block_data(asset_name)


def save_block_data(asset_name: str, data: BlockData) -> Path:
    return _save_block_data(asset_name, data)


def load_group_records(asset_name: str) -> list[GroupRecord]:
    return _load_group_records(asset_name)


def create_group_record(asset_name: str, block_ids: list[int], group_idx: int | None = None) -> GroupRecord:
    return _create_group_record(asset_name, block_ids, group_idx=group_idx)


def delete_group_record(asset_name: str, group_idx: int) -> None:
    _delete_group_record(asset_name, group_idx)


def init_tutor(asset_name: str, group_idx: int, focus_markdown: str) -> Path:
    return _init_tutor(asset_name, group_idx, focus_markdown)


def list_assets() -> list[str]:
    return _list_assets()


__all__ = [
    "BlockData",
    "BlockRecord",
    "BlockRect",
    "GroupRecord",
    "create_group_record",
    "delete_group_record",
    "get_asset_dir",
    "get_asset_pdf_path",
    "init_tutor",
    "list_assets",
    "load_asset_config",
    "load_block_data",
    "load_group_records",
    "save_asset_config",
    "save_block_data",
]
