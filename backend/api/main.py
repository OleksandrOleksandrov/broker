import asyncio
import base64
import io
import logging
import os
import time
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from openai import AsyncOpenAI, OpenAI
from openpyxl import Workbook
from pdf2image import convert_from_bytes
from PIL import Image
from pypdf import PdfReader, PdfWriter

if __package__:
    from .models import (
        ApplicationItem,
        CMRCargoItem,
        CMRDocument,
        CMRParty,
        CMRVehicle,
        CombinedDocumentData,
        CombinedDocumentSummary,
        InvoiceData,
        InvoiceItem,
        PartyDetails,
        TransportDocumentsRow,
        UktZedSuggestion,
        _build_transport_documents_row,
        _identify_file_type,
        find_suspicious_address_token,
    )
else:
    from models import (
        ApplicationItem,
        CMRCargoItem,
        CMRDocument,
        CMRParty,
        CMRVehicle,
        CombinedDocumentData,
        CombinedDocumentSummary,
        InvoiceData,
        InvoiceItem,
        PartyDetails,
        TransportDocumentsRow,
        UktZedSuggestion,
        _build_transport_documents_row,
        _identify_file_type,
        find_suspicious_address_token,
    )

load_dotenv()

logger = logging.getLogger("broker.api")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger.setLevel(os.getenv("LOG_LEVEL", "INFO"))

# Lambda layer binary path for Poppler
POPPLER_PATH = os.getenv("POPPLER_PATH")

gpt_model = os.getenv("GPT_MODEL", "gpt-4o-2024-11-20")
api_key = os.getenv("OPENAI_API_KEY")
dpi = int(os.getenv("PDF_DPI", "300"))  # Default DPI for PDF to image conversion

app = FastAPI(
    title="Broker AI Assistant",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)


# Дозволяємо запити з Node.js фронтенду
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request, call_next):
    """Log every API request and its response status."""
    started_at = time.perf_counter()
    logger.info("Request started: %s %s", request.method, request.url.path)
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = (time.perf_counter() - started_at) * 1000
        logger.exception(
            "Request failed: %s %s (%.1f ms)",
            request.method,
            request.url.path,
            duration_ms,
        )
        raise
    duration_ms = (time.perf_counter() - started_at) * 1000
    logger.info(
        "%s %s -> %s (%.1f ms)",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


def encode_image_to_base64(image: Image.Image) -> str:
    buffered = io.BytesIO()
    image.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")


async def convert_pdf_to_images(pdf_bytes: bytes, dpi: int) -> list[Image.Image]:
    """Run the blocking Poppler conversion outside the event loop."""
    kwargs = {"dpi": dpi}
    if POPPLER_PATH:
        kwargs["poppler_path"] = POPPLER_PATH
    return await asyncio.to_thread(convert_from_bytes, pdf_bytes, **kwargs)


async def build_image_payload(images: list[Image.Image]) -> list[dict]:
    encoded_images = await asyncio.gather(
        *(asyncio.to_thread(encode_image_to_base64, image) for image in images)
    )
    return [
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{encoded_image}"},
        }
        for encoded_image in encoded_images
    ]


def encode_lossless_image_to_base64(image: Image.Image) -> str:
    buffered = io.BytesIO()
    image.save(buffered, format="PNG", optimize=True)
    return base64.b64encode(buffered.getvalue()).decode("utf-8")


def encode_lossless_image_to_base64(image: Image.Image) -> str:
    buffered = io.BytesIO()
    image.save(buffered, format="PNG", optimize=True)
    return base64.b64encode(buffered.getvalue()).decode("utf-8")


# 2. Функція підбору коду УКТ ЗЕД для конкретної позиції
def get_uktzed_code(
    client: OpenAI, item_description: str, article: Optional[str]
) -> UktZedSuggestion:
    prompt = f"Товар: {item_description}. Артикул: {article or 'не вказано'}."

    completion = client.beta.chat.completions.parse(
        model=gpt_model,
        messages=[
            {
                "role": "system",
                "content": "Ти експерт з митної класифікації товарів за митним тарифом України (УКТ ЗЕД). "
                "Визнач найбільш вірогідний 10-значний код УКТ ЗЕД та надай обґрунтування.",
            },
            {"role": "user", "content": prompt},
        ],
        response_format=UktZedSuggestion,
        temperature=0.0,
    )
    return completion.choices[0].message.parsed


# 3. Ендпоінт обробки PDF
@app.post("/api/parse-invoice", response_model=InvoiceData)
async def parse_invoice(
    file: UploadFile = File(...),
    parse_uktzed: bool = Form(False),
):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500, detail="OPENAI_API_KEY не знайдено в оточенні"
        )

    client = AsyncOpenAI(api_key=api_key)
    pdf_bytes = await file.read()
    logger.info(
        "Parsing invoice file=%s size=%d bytes parse_uktzed=%s",
        file.filename,
        len(pdf_bytes),
        parse_uktzed,
    )
    try:
        # Вказуємо poppler_path для зчитування бінарників з Lambda Layer
        images = await convert_pdf_to_images(pdf_bytes, dpi=350)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Помилка зчитування PDF: {str(e)}")

    content_payload = [
        {
            "type": "text",
            "text": (
                "Carefully extract all invoice data and line items in a structured format. "
                "For every line item, extract net_weight_kg when the net weight is visible; "
                "otherwise leave it null."
            ),
        }
    ]

    content_payload.extend(await build_image_payload(images))

    # Витягуємо дані інвойсу через Vision API
    try:
        completion = await client.beta.chat.completions.parse(
            model=gpt_model,
            messages=[
                {
                    "role": "system",
                    "content": "Ти професійний експерт з декларування та митного оформлення. "
                    "Точно зчитуй дані з документів без фантазування.",
                },
                {"role": "user", "content": content_payload},
            ],
            response_format=InvoiceData,
            temperature=0.0,
        )
    except Exception:
        logger.exception("OpenAI invoice parsing failed for file=%s", file.filename)
        raise

    parsed_data = completion.choices[0].message.parsed

    # Підбираємо коди УКТ ЗЕД лише за запитом користувача (чекбокс у фронтенді)
    if parse_uktzed and parsed_data.items:
        logger.info(
            "UKT ZED classification requested for %d item(s)", len(parsed_data.items)
        )

        async def classify(item: InvoiceItem) -> None:
            try:
                item.uktzed_suggestion = await asyncio.to_thread(
                    get_uktzed_code, client, item.description, item.article
                )
            except Exception as e:
                logger.exception("UKT ZED classification failed for item: %s", e)
                item.uktzed_suggestion = UktZedSuggestion(
                    code="0000000000",
                    description="Не вдалося визначити",
                    justification="Помилка при запиті класифікації",
                )

        await asyncio.gather(*(classify(item) for item in parsed_data.items))
    else:
        # Якщо класифікація не потрібна — явно очищаємо поле,
        # щоб клієнт не отримав застарілі дані
        for item in parsed_data.items:
            item.uktzed_suggestion = None

    return parsed_data


@app.post("/api/parse-application", response_model=ApplicationItem)
async def parse_application(
    file: UploadFile = File(...),
):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500, detail="OPENAI_API_KEY не знайдено в оточенні"
        )

    client = AsyncOpenAI(api_key=api_key)
    pdf_bytes = await file.read()
    try:
        images = await convert_pdf_to_images(pdf_bytes, dpi=dpi)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Помилка зчитування PDF: {str(e)}")

    content_payload = [
        {
            "type": "text",
            "text": (
                "Це українська заявка на перевезення вантажу (транспортна заявка). "
                "Уважно витягни всі реквізити: номер і дату заявки, номер і дату договору, "
                "маршрут, адреси завантаження/розвантаження/замитнення/розмитнення, дати та час, "
                "дані про вантаж, транспортний засіб, водія, відповідальну особу Замовника, "
                "ціну та юридичні реквізити обох сторін (Замовника і Перевізника). "
                "Для кожної адреси (loading_address, customs_outbound_address, "
                "customs_inbound_address, unloading_address) продублюй також точний "
                "фрагмент тексту з документа, з якого ти її прочитав, у відповідному "
                "*_source полі. Не вигадуй значень — якщо поле відсутнє, залиш null."
            ),
        }
    ]

    content_payload.extend(await build_image_payload(images))

    system_prompt = (
        "Ти професійний логіст. Точно зчитуй дані з документа без фантазування.\n"
        "ПРАВИЛО ЩОДО АДРЕС: в українських номерах будинків після '/' або '-' зазвичай "
        "стоїть ЛІТЕРА, а не цифра (1/б, 25-А, 48В). Копіюй символи як у документі, не "
        "замінюй кириличні літери на схожі цифри.\n"
        "Приклад: 'вул. Хмельницького, 1/б' — коректно як '1/б', НЕ як '1/6'."
    )

    async def _extract(retry_hint: Optional[str] = None) -> ApplicationItem:
        user_text = content_payload[0]["text"]
        if retry_hint:
            user_text = (
                user_text + "\n\nУВАГА: попередня відповідь містила підозрілий токен "
                f"{retry_hint!r} (цифра після '/' або '-' у номері будинку). "
                "Перечитай адресу в документі та виправ її. Після '/' або '-' має стояти ЛІТЕРА."
            )
        payload = [{"type": "text", "text": user_text}, *content_payload[1:]]
        completion = await client.beta.chat.completions.parse(
            model=gpt_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": payload},
            ],
            response_format=ApplicationItem,
            temperature=0.0,
        )
        return completion.choices[0].message.parsed

    parsed = await _extract()
    for _attempt in range(2):
        offending = find_suspicious_address_token(parsed)
        if not offending:
            break
        logger.warning(
            "parse_application: suspicious address token %r, retrying with hint",
            offending,
        )
        parsed = await _extract(retry_hint=offending)

    return parsed


@app.post("/api/export-excel")
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


@app.post("/api/compress-pdf")
async def compress_pdf(
    file: UploadFile = File(...),
    max_size_kb: int = Form(500),
    remove_color: bool = Form(True),
):
    if not file.content_type or "pdf" not in file.content_type.lower():
        raise HTTPException(status_code=400, detail="Файл має бути PDF")
    DPI = 150
    pdf_bytes = await file.read()
    max_size_bytes = max_size_kb * 1024

    reader = PdfReader(io.BytesIO(pdf_bytes))
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    for page in writer.pages:
        page.compress_content_streams()

    buf = io.BytesIO()
    writer.write(buf)
    compressed = buf.getvalue()

    def _try_grayscale(dpi: int) -> bytes:
        if POPPLER_PATH:
            images = convert_from_bytes(pdf_bytes, dpi=dpi, poppler_path=POPPLER_PATH)
        else:
            images = convert_from_bytes(pdf_bytes, dpi=dpi)
        gray_images = [img.convert("L") for img in images]
        out = io.BytesIO()
        gray_images[0].save(
            out,
            format="PDF",
            save_all=True,
            append_images=gray_images[1:],
            resolution=dpi,
            optimize=True,
        )
        return out.getvalue()

    def _try_quality(dpi: int, quality: int) -> bytes:
        if POPPLER_PATH:
            images = convert_from_bytes(pdf_bytes, dpi=dpi, poppler_path=POPPLER_PATH)
        else:
            images = convert_from_bytes(pdf_bytes, dpi=dpi)
        if remove_color:
            images = [img.convert("L") for img in images]
        out = io.BytesIO()
        images[0].save(
            out,
            format="PDF",
            save_all=True,
            append_images=images[1:],
            resolution=dpi,
            optimize=True,
            quality=quality,
        )
        return out.getvalue()

    if len(compressed) > max_size_bytes:
        logger.info(
            "Initial lossless size=%d bytes, target=%d bytes",
            len(compressed),
            max_size_bytes,
        )

        if remove_color:
            try:
                compressed = _try_grayscale(DPI)
                logger.info("Grayscale size=%d bytes", len(compressed))
                if len(compressed) <= max_size_bytes:
                    pass
            except Exception:
                logger.exception("Grayscale compression attempt failed")

        if len(compressed) > max_size_bytes:
            quality = 95
            while len(compressed) > max_size_bytes and quality >= 40:
                try:
                    compressed = _try_quality(DPI, quality)
                    logger.info("Quality=%d size=%d bytes", quality, len(compressed))
                    if len(compressed) <= max_size_bytes:
                        break
                except Exception:
                    logger.exception("Quality compression attempt failed")
                    break
                quality -= 5

        if len(compressed) > max_size_bytes:
            dpi = 150
            while len(compressed) > max_size_bytes and dpi >= 50:
                quality = 95
                while len(compressed) > max_size_bytes and quality >= 40:
                    try:
                        compressed = _try_quality(dpi, quality)
                        logger.info(
                            "DPI=%d quality=%d size=%d bytes",
                            dpi,
                            quality,
                            len(compressed),
                        )
                        if len(compressed) <= max_size_bytes:
                            break
                    except Exception:
                        logger.exception("DPI/quality compression attempt failed")
                        break
                    quality -= 5
                if len(compressed) <= max_size_bytes:
                    break
                dpi -= 25

    if len(compressed) > max_size_bytes:
        raise HTTPException(
            status_code=422,
            detail=f"Не вдалося стиснути PDF до {max_size_kb} KB. Мінімальний досяжний розмір: {len(compressed) // 1024} KB",
        )

    filename = f"compressed_{file.filename or 'document'}.pdf"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(
        io.BytesIO(compressed),
        headers=headers,
        media_type="application/pdf",
    )




@app.post("/api/parse-cmr", response_model=CMRDocument)
async def parse_cmr(
    file: UploadFile = File(...),
):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500, detail="OPENAI_API_KEY не знайдено в оточенні"
        )

    client = AsyncOpenAI(api_key=api_key)
    pdf_bytes = await file.read()
    try:
        images = await convert_pdf_to_images(pdf_bytes, dpi=dpi)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Помилка зчитування PDF: {str(e)}")

    content_payload = [
        {
            "type": "text",
            "text": (
                "Це міжнародна транспортна накладна CMR. Уважно витягни всі видимі "
                "реквізити документа у структурований формат. Зчитай номер CMR, "
                "відправника, одержувача, місця завантаження та доставки, додані "
                "документи, усі рядки вантажу, інструкції, перевізників, умови "
                "оплати, застереження, спеціальні умови, дати й час, номери "
                "дорожнього листа, водіїв, дані автомобіля та підпис одержувача. "
                "Для полів, яких немає або які неможливо прочитати, поверни null; "
                "cargo_items має містити лише фактично наявні рядки вантажу. "
                "Не вигадуй значень і не виправляй написання назв, номерів чи адрес."
            ),
        }
    ]

    content_payload.extend(await build_image_payload(images))

    completion = await client.beta.chat.completions.parse(
        model=gpt_model,
        messages=[
            {
                "role": "system",
                "content": (
                    "Ти професійний фахівець з міжнародних вантажних перевезень. "
                    "Точно зчитуй дані з CMR без фантазування. Зберігай оригінальне "
                    "написання та одиниці виміру."
                ),
            },
            {"role": "user", "content": content_payload},
        ],
        response_format=CMRDocument,
        temperature=0.0,
    )

    return completion.choices[0].message.parsed


@app.post("/api/parse-transport-documents", response_model=CombinedDocumentData)
async def parse_transport_documents(
    invoice_file: UploadFile = File(...),
    application_file: UploadFile = File(...),
    cmr_file: UploadFile = File(...),
    parse_uktzed: bool = Form(False),
):
    # Parse an invoice, transport application, and CMR in one request.
    invoice, application, cmr = await asyncio.gather(
        parse_invoice(invoice_file, parse_uktzed),
        parse_application(application_file),
        parse_cmr(cmr_file),
    )

    net_weights = [
        item.net_weight_kg for item in invoice.items if item.net_weight_kg is not None
    ]
    def _normalize_quotes(text: str | None) -> str | None:
        if text is None:
            return None
        result = []
        use_open = True
        for char in text:
            if char == '"':
                result.append("«" if use_open else "»")
                use_open = not use_open
            else:
                result.append(char)
        return "".join(result)

    carrier = (
        _normalize_quotes(application.carrier_details.name)
        if application.carrier_details
        else _normalize_quotes(cmr.carrier.name_and_address) if cmr.carrier else None
    )

    nomenclature = [item.oil_group for item in invoice.items]
    if not nomenclature:
        nomenclature = [
            item.name_of_goods for item in cmr.cargo_items if item.name_of_goods
        ]

    summary = CombinedDocumentSummary(
        contract=invoice.contract_number,
        net_weight_kg=sum(net_weights) if net_weights else None,
        border_crossing_point=application.border_crossing_point,
        carrier=carrier,
        nomenclature=nomenclature,
        unloading_city=cmr.delivery_city.upper() or application.unloading_city.upper(),
        invoice_number=invoice.contract_number,
        vn_number_pd=invoice.contract_number,
        vehicle_number="".join(application.vehicle_info.split()),
        tax_document_number=invoice.contract_number,
    )
    return CombinedDocumentData(
        summary=summary,
        invoice=invoice,
        application=application,
        cmr=cmr,
    )


@app.post(
    "/api/parse-transport-documents-row",
    response_model=TransportDocumentsRow,
)
async def parse_transport_documents_row(
    files: List[UploadFile] = File(...),
    parse_uktzed: bool = Form(False),
):
    """Parse three transport documents and return a flat row of strings
    matching the legacy Spark `val(...)` column layout.
    Files can be uploaded in any order; type is determined from filename.
    """
    if len(files) != 3:
        raise HTTPException(status_code=400, detail="Exactly 3 files are required")

    invoice_file = None
    application_file = None
    cmr_file = None

    for file in files:
        file_type = _identify_file_type(file.filename or "")
        if file_type == "invoice":
            invoice_file = file
        elif file_type == "application":
            application_file = file
        elif file_type == "cmr":
            cmr_file = file

    missing = []
    if not invoice_file:
        missing.append("invoice")
    if not application_file:
        missing.append("application")
    if not cmr_file:
        missing.append("cmr")

    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Could not identify file types for: {', '.join(missing)}. "
                   f"Filenames must contain 'invoice'/'інвойс'/'инвойс'/'накладна'/'счёт', "
                   f"'application'/'заявка'/'заявление', or 'cmr' respectively.",
        )

    data = await parse_transport_documents(
        invoice_file=invoice_file,
        application_file=application_file,
        cmr_file=cmr_file,
        parse_uktzed=parse_uktzed,
    )
    values = _build_transport_documents_row(data)
    return TransportDocumentsRow(
        contract=values[0],
        blank_1=values[1],
        net_weight_kg=values[2] or None,
        border_crossing_point=values[3],
        carrier=values[4],
        nomenclature=values[5],
        unloading_city=values[6],
        blank_2=values[7],
        vehicle_number=values[8],
        values=values,
    )
