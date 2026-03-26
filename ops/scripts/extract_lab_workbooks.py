#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import pandas as pd


def workbook_slug(path: Path) -> str:
    match = re.search(r"(\d{8})", path.stem)
    if match:
        return match.group(1)
    return path.stem.lower()


def stringify(value: Any) -> str:
    if pd.isna(value):
        return ""
    if hasattr(value, "strftime"):
        try:
            return value.strftime("%Y-%m-%d %H:%M:%S").strip()
        except Exception:
            pass
    text = str(value).strip()
    if text == "nan":
        return ""
    return text


def dedupe_headers(headers: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    deduped: list[str] = []
    for index, header in enumerate(headers, start=1):
        base = header or f"列{index}"
        count = seen.get(base, 0)
        seen[base] = count + 1
        deduped.append(base if count == 0 else f"{base}_{count + 1}")
    return deduped


def normalize_header(header: str) -> str:
    value = header.strip()
    if value.lower() == "time":
        return "时间"
    return value


def infer_sheet_type(sheet_name: str, frame: pd.DataFrame) -> str:
    first_row = [stringify(cell) for cell in frame.iloc[0].tolist()] if not frame.empty else []
    joined = " ".join(filter(None, first_row))
    if (
        any(token in joined for token in ["SR", "真实"]) or
        all(token in joined for token in ["序号", "能量", "离焦"])
    ):
        return "calibration"
    if any(token in joined for token in ["时间", "time", "No", "压缩后"]):
        return "main_log"
    if any(token in joined for token in ["任务序号", "打靶计划", "计划"]):
        return "plan"
    if any(token in joined for token in ["靶位", "靶块", "空发"]):
        return "target_grid"
    return "matrix"


def extract_main_log(frame: pd.DataFrame) -> dict[str, Any]:
    rows = frame.fillna("")
    headers = dedupe_headers([normalize_header(stringify(cell)) for cell in rows.iloc[0].tolist()])
    items: list[dict[str, str]] = []
    for row_index in range(1, len(rows)):
        values = [stringify(cell) for cell in rows.iloc[row_index].tolist()]
        if not any(values):
            continue
        items.append({
            header: values[index] if index < len(values) else ""
            for index, header in enumerate(headers)
        })
    return {
        "columns": headers,
        "rows": items,
    }


def extract_matrix(frame: pd.DataFrame) -> dict[str, Any]:
    rows = [
        [stringify(cell) for cell in record]
        for record in frame.fillna("").values.tolist()
    ]
    while rows and not any(rows[-1]):
        rows.pop()
    return {"rows": rows}


def extract_sheet(sheet_name: str, frame: pd.DataFrame, position: int) -> dict[str, Any]:
    sheet_type = infer_sheet_type(sheet_name, frame)
    payload = extract_main_log(frame) if sheet_type == "main_log" else extract_matrix(frame)
    return {
        "sheet_key": f"sheet{position}",
        "sheet_name": sheet_name,
        "type": sheet_type,
        "position": position,
        **payload,
    }


def extract_workbook(path: Path) -> dict[str, Any]:
    with pd.ExcelFile(path) as excel:
        sheets = [
            extract_sheet(sheet_name, pd.read_excel(path, sheet_name=sheet_name, header=None), index + 1)
            for index, sheet_name in enumerate(excel.sheet_names)
        ]
    return {
        "slug": workbook_slug(path),
        "title": f"实验工作簿 {workbook_slug(path)}",
        "source_filename": path.name,
        "run_label": "",
        "sheets": sheets,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract real experiment Excel files into LabWorkbook seed JSON.")
    parser.add_argument("paths", nargs="+", type=Path, help="Workbook files to extract")
    parser.add_argument("--output-dir", type=Path, required=True, help="Directory for generated JSON")
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    for workbook_path in args.paths:
        workbook = extract_workbook(workbook_path)
        output_path = args.output_dir / f"{workbook['slug']}.json"
        output_path.write_text(
            json.dumps(workbook, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
