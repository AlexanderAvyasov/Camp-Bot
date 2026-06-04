"""Excel import logic for children.

Supports the camp's standard format where each child spans 2 rows:
  Row 1: №, full_name, voucher, birth_date, address, father (О:...), workplace, phone
  Row 2: (empty), (empty), ...,            mother (М:...), workplace, phone

Squad name is extracted from the sheet header row that contains
"СПИСОК ОТРЯДА" or similar patterns.
"""
import re
from datetime import date, datetime
from typing import IO

import openpyxl

# Prefix → relation label
def _to_str(value) -> str | None:
    """Convert a cell value to string, handling floats like 3930.0 → '3930'."""
    if value is None:
        return None
    if isinstance(value, float):
        return str(int(value)) if value == int(value) else str(value)
    return str(value).strip() or None


_RELATION_PREFIXES = {
    "о:": "Отец",
    "м:": "Мать",
    "д:": "Дедушка",
    "б:": "Бабушка",
    "оп:": "Опекун",
}


def _parse_date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    s = str(value).strip()
    for fmt in ("%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d", "%d.%m.%y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def _parse_parent(raw: str | None, phone_raw) -> dict | None:
    """Parse a parent entry like 'О:Иванов Иван' or plain name."""
    if not raw:
        return None
    raw = raw.strip()
    if not raw or raw == "-":
        return None

    relation = "Родитель"
    name = raw
    low = raw.lower()
    for prefix, rel in _RELATION_PREFIXES.items():
        if low.startswith(prefix):
            relation = rel
            name = raw[len(prefix):].strip()
            break

    phone = None
    if phone_raw is not None:
        phone_str = _to_str(phone_raw)
        if phone_str and phone_str != "-":
            phone = phone_str

    return {"full_name": name, "phone": phone, "relation": relation}


def _extract_squad_from_sheet(ws) -> str | None:
    """Scan first 10 rows for a line containing squad/squad-number info."""
    for row in ws.iter_rows(max_row=10, values_only=True):
        for cell in row:
            if cell and isinstance(cell, str):
                m = re.search(r"список\s+отряда\s*[№#]?\s*(\d+)", cell, re.IGNORECASE)
                if m:
                    return m.group(1)
                m = re.search(r"отряд\s*[№#]?\s*(\d+)", cell, re.IGNORECASE)
                if m:
                    return m.group(1)
    return None


def _find_header_row(ws):
    """Return (row_index_0based, row_values) of the row that has child-list headers."""
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        cells = [str(c).strip().lower() if c else "" for c in row]
        if any("ф.и.о" in c or "фио" in c or "ребен" in c for c in cells):
            return i, row
    return None, None


def parse_excel(file: IO[bytes]) -> tuple[list[dict], list[str]]:
    """
    Parse camp Excel roster.

    Returns (rows, warnings).  Each row dict has:
      full_name, birth_date, squad_name, dormitory, food_type,
      allergies, medications, raw_data (dict), parents (list of dicts).
    """
    wb = openpyxl.load_workbook(file, data_only=True)
    results: list[dict] = []
    warnings: list[str] = []

    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]

        # Skip obviously empty sheets
        if ws.max_row < 3:
            continue

        squad_from_header = _extract_squad_from_sheet(ws)
        header_row_idx, header_row = _find_header_row(ws)

        if header_row is None:
            # Fallback: try generic flat import
            _parse_flat_sheet(ws, squad_from_header, results, warnings, sheet_name)
            continue

        # Build column index map from the header row
        # Columns we care about (by position after finding them):
        col_num = None          # №  — presence marks a new child row
        col_name = None         # Ф.И.О. ребёнка
        col_voucher = None      # № путевки
        col_birth = None        # Дата рождения
        col_address = None      # Адрес
        col_parent_fio = None   # Ф.И.О. родителей
        col_workplace = None    # Место работы
        col_phone = None        # Телефон
        col_squad = None        # Отряд (if present)
        col_dormitory = None    # Корпус
        col_food = None         # Питание

        for ci, cell in enumerate(header_row):
            if cell is None:
                continue
            h = str(cell).strip().lower()
            if h in ("№", "n", "n°", "#"):
                col_num = ci
            elif "ф.и.о" in h and ("ребен" in h or "детей" in h or col_name is None):
                col_name = ci
            elif "путевк" in h or "voucher" in h:
                col_voucher = ci
            elif "дата" in h or "д.р" in h or "рожд" in h:
                col_birth = ci
            elif "адрес" in h:
                col_address = ci
            elif "родител" in h or ("ф.и.о" in h and ci != col_name):
                col_parent_fio = ci
            elif "место работы" in h or "работа" in h:
                col_workplace = ci
            elif "телефон" in h or "тел." in h:
                col_phone = ci
            elif "отряд" in h:
                col_squad = ci
            elif "корпус" in h or "домик" in h:
                col_dormitory = ci
            elif "питание" in h or "питан" in h:
                col_food = ci

        if col_name is None:
            warnings.append(f"Лист «{sheet_name}»: не найдена колонка с именем ребёнка")
            continue

        # Read data rows (everything after header)
        all_rows = list(ws.iter_rows(values_only=True))
        data_rows = all_rows[header_row_idx + 1:]

        # Group rows: a child row has a number in col_num (or col_name not empty)
        # The following rows with no number belong to the same child (extra parents)
        current_child: dict | None = None

        for row_offset, row in enumerate(data_rows):
            if not any(c is not None for c in row):
                continue

            def get(ci):
                if ci is None or ci >= len(row):
                    return None
                v = row[ci]
                return v

            is_child_row = (
                (col_num is not None and get(col_num) is not None and str(get(col_num)).strip().isdigit())
                or (col_num is None and get(col_name) is not None)
            )

            if is_child_row:
                if current_child is not None:
                    results.append(current_child)

                name_val = get(col_name)
                full_name = str(name_val).strip() if name_val else None
                if not full_name:
                    current_child = None
                    continue

                squad_name = squad_from_header
                if col_squad is not None and get(col_squad):
                    squad_name = str(get(col_squad)).strip()

                raw_data: dict = {}
                if col_address is not None and get(col_address):
                    raw_data["Адрес"] = str(get(col_address)).strip()
                if col_voucher is not None and get(col_voucher):
                    raw_data["voucher"] = _to_str(get(col_voucher))

                current_child = {
                    "full_name": full_name,
                    "birth_date": _parse_date(get(col_birth)) if col_birth is not None else None,
                    "squad_name": squad_name,
                    "dormitory": str(get(col_dormitory)).strip() if col_dormitory is not None and get(col_dormitory) else None,
                    "food_type": str(get(col_food)).strip() if col_food is not None and get(col_food) else None,
                    "allergies": None,
                    "medications": None,
                    "raw_data": raw_data,
                    "parents": [],
                }

                parent = _parse_parent(
                    str(get(col_parent_fio)).strip() if col_parent_fio is not None and get(col_parent_fio) else None,
                    get(col_phone) if col_phone is not None else None,
                )
                if parent:
                    current_child["parents"].append(parent)

            else:
                # Continuation row — extra parent line for the current child
                if current_child is None:
                    continue
                parent = _parse_parent(
                    str(get(col_parent_fio)).strip() if col_parent_fio is not None and get(col_parent_fio) else None,
                    get(col_phone) if col_phone is not None else None,
                )
                if parent:
                    current_child["parents"].append(parent)

        if current_child is not None:
            results.append(current_child)

    return results, warnings


def _parse_flat_sheet(ws, squad_name, results, warnings, sheet_name):
    """Fallback: simple flat rows with COLUMN_MAP headers."""
    COLUMN_MAP = {
        "фио": "full_name", "полное имя": "full_name", "имя": "full_name",
        "ф.и.о. ребенка": "full_name", "ф.и.о.ребенка": "full_name",
        "дата рождения": "birth_date", "д.р.": "birth_date", "дата рожд.": "birth_date",
        "отряд": "squad_name", "корпус": "dormitory",
        "питание": "food_type", "аллергии": "allergies", "медикаменты": "medications",
        "родитель 1": "parent1_name", "телефон": "parent1_phone",
        "родитель 2": "parent2_name",
    }

    rows_iter = ws.iter_rows(values_only=True)
    headers_raw = None
    for row in rows_iter:
        if any(c is not None for c in row):
            headers_raw = row
            break
    if not headers_raw:
        return

    headers = [str(h).strip().lower() if h else "" for h in headers_raw]
    mapped = [COLUMN_MAP.get(h) for h in headers]

    for row_num, row in enumerate(rows_iter, start=2):
        if not any(c is not None for c in row):
            continue
        record: dict = {"raw_data": {}, "parents": []}
        p1_name = p1_phone = p2_name = p2_phone = None

        for ci, (val, field) in enumerate(zip(row, mapped)):
            if field is None:
                h = headers[ci]
                if h and val is not None:
                    record["raw_data"][h] = str(val)
                continue
            if field == "birth_date":
                record["birth_date"] = _parse_date(val)
            elif field == "parent1_name":
                p1_name = str(val).strip() if val else None
            elif field == "parent1_phone":
                p1_phone = str(val).strip() if val else None
            elif field == "parent2_name":
                p2_name = str(val).strip() if val else None
            elif field == "parent2_phone":
                p2_phone = str(val).strip() if val else None
            else:
                record[field] = str(val).strip() if val else None

        if not record.get("full_name"):
            continue
        record.setdefault("squad_name", squad_name)
        record.setdefault("birth_date", None)
        record.setdefault("dormitory", None)
        record.setdefault("food_type", None)
        record.setdefault("allergies", None)
        record.setdefault("medications", None)

        if p1_name:
            record["parents"].append({"full_name": p1_name, "phone": p1_phone, "relation": "Родитель"})
        if p2_name:
            record["parents"].append({"full_name": p2_name, "phone": p2_phone, "relation": "Родитель 2"})

        results.append(record)
