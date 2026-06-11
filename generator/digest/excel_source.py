"""
엑셀 필드 사전 소스 — 용어/단위/그룹을 제공해 숫자 오독을 막는다.
파일: data/241118 금형 필드 설명_수정.xlsx  (2열: 필드명 / 설명)
"""
import re

import openpyxl

from schemas import FieldSpec


def _infer_group(name: str) -> str:
    n = name.strip()
    if re.match(r"^T\d", n):
        return "temp"
    if re.match(r"^P\d", n):
        return "pressure"
    if n.startswith("ProcessTime") or n == "CycleInterval":
        return "time"
    if n in {"Cycle", "StartTime", "EndTime", "Model", "PartName", "PartNo", "MoldNo"}:
        return "id"
    if n in {"Resin", "Grade"}:
        return "material"
    if n in {"Condition", "Sequence"}:
        return "condition"
    return "etc"


def _infer_unit(name: str, group: str) -> str | None:
    if group == "temp":
        return "°C"
    if group == "time":
        return "ms" if name.startswith("ProcessTime") else "sec"
    return None


class ExcelSource:
    name = "excel"

    def __init__(self, path: str):
        self.path = path

    def field_dict(self) -> dict[str, FieldSpec]:
        wb = openpyxl.load_workbook(self.path, data_only=True)
        ws = wb.active
        out: dict[str, FieldSpec] = {}
        for row in ws.iter_rows(min_row=2, values_only=True):  # 1행은 헤더
            if not row or not row[0]:
                continue
            name = str(row[0]).strip()
            desc = str(row[1]).strip() if len(row) > 1 and row[1] else ""
            group = _infer_group(name)
            out[name] = FieldSpec(name=name, group=group,
                                  unit=_infer_unit(name, group), description=desc)
        return out
