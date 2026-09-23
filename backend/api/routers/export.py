"""Export router."""

import io
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from openpyxl import Workbook

from ..models import InvoiceData

router = APIRouter(prefix="/api", tags=["export"])


@router.post("/export-excel")
async def export_excel(data: InvoiceData):
    rows = []
    for idx, item in enumerate(data.items, 1):
        uktzed_code = item.uktzed_suggestion.code if item.uktzed_suggestion else ""

        rows.append(
            {
                "№": item.item_number or idx,
                "Артикул": item.article or "",
                "Найменування товару (Графа 31)": item.description,
                "Код УКТ ЗЕД (Графа 33)": uktzed_code,
                "Кількість": item.quantity,
                "Од. виміру": item.unit,
                "Ціна": item.price_per_unit,
                "Фактурна вартість": item.total_amount,
                "Країна походження": item.country_of_origin or "",
                "Валюта": data.currency or "",
            }
        )

    output = io.BytesIO()
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Specification"
    headers = (
        list(rows[0])
        if rows
        else [
            "№",
            "Артикул",
            "Найменування товару (Графа 31)",
            "Код УКТ ЗЕД (Графа 33)",
            "Кількість",
            "Од. виміру",
            "Ціна",
            "Фактурна вартість",
            "Країна походження",
            "Валюта",
        ]
    )
    worksheet.append(headers)
    for row in rows:
        worksheet.append([row[header] for header in headers])
    workbook.save(output)
    output.seek(0)

    headers = {
        "Content-Disposition": 'attachment; filename="md_declaration_import.xlsx"'
    }
    return StreamingResponse(
        output,
        headers=headers,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )