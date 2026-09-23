import React, { useState, ChangeEvent } from 'react';
import type {
  InvoiceData,
  ApplicationData,
  CMRDocument,
  CombinedSummary,
  CombinedDocumentData,
  FilePickerProps,
} from '@/types';

const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
).replace(/\/$/, '');

function FilePicker<T extends File | File[] | null>({
  label,
  accept,
  onChange,
  selectedFile,
  multiple = false,
  disabled,
}: FilePickerProps<T>): React.JSX.Element {
  const selectedFiles = Array.isArray(selectedFile)
    ? selectedFile
    : selectedFile
      ? [selectedFile]
      : [];

  return (
    <div className="flex items-center gap-2">
      <label className="relative inline-flex items-center">
        <input
          type="file"
          accept={accept}
          multiple={multiple}
          onChange={(e) => {
            if (multiple) {
              const files = e.target.files ? Array.from(e.target.files) : [];
              onChange((files.length > 0 ? files : null) as T);
            } else if (e.target.files && e.target.files[0]) {
              onChange(e.target.files[0] as T);
            } else {
              onChange(null as T);
            }
            e.target.value = '';
          }}
          disabled={disabled}
          className="hidden"
        />
        <span className="bg-gray-200 hover:bg-gray-300 disabled:bg-gray-100 text-gray-800 font-semibold px-4 py-2 rounded cursor-pointer transition-colors">
          {label}
        </span>
      </label>
      <span className="text-sm text-gray-600 truncate">
        {selectedFiles.length > 0
          ? selectedFiles.length === 1
            ? selectedFiles[0].name
            : `${selectedFiles.length} файлів обрано`
          : 'Файл не обрано'}
      </span>
    </div>
  );
}

function identifyFileType(filename: string): 'invoice' | 'application' | 'cmr' | 'unknown' {
  const name = filename.toLowerCase();
  if (name.normalize().includes('cmr'.normalize()) || name.normalize().includes('срм'.normalize())) {
    return 'cmr';
  }
  if (
    name.normalize().includes('invoice'.normalize()) ||
    name.normalize().includes('інвойс'.normalize()) ||
    name.normalize().includes('инвойс'.normalize()) ||
    name.normalize().includes('накладна'.normalize()) ||
    name.normalize().includes('счёт'.normalize()) ||
    name.normalize().includes('счет'.normalize())
  ) {
    return 'invoice';
  }
  if (
    name.normalize().includes('application'.normalize()) ||
    name.normalize().includes('заявка'.normalize()) ||
    name.normalize().includes('заявление'.normalize()) ||
    name.normalize().includes('заява'.normalize())
  ) {
    return 'application';
  }
  return 'unknown';
}

export default function InvoiceParserApp(): React.JSX.Element {
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [data, setData] = useState<InvoiceData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [parseUktzed, setParseUktzed] = useState<boolean>(false);
  const [applicationFile, setApplicationFile] = useState<File | null>(null);
  const [applicationData, setApplicationData] = useState<ApplicationData | null>(null);
  const [applicationLoading, setApplicationLoading] = useState<boolean>(false);
  const [applicationError, setApplicationError] = useState<string | null>(null);
  const [cmrFile, setCmrFile] = useState<File | null>(null);
  const [cmrData, setCmrData] = useState<CMRDocument | null>(null);
  const [cmrLoading, setCmrLoading] = useState<boolean>(false);
  const [cmrError, setCmrError] = useState<string | null>(null);
  const [combinedLoading, setCombinedLoading] = useState<boolean>(false);
  const [combinedError, setCombinedError] = useState<string | null>(null);
  const [combinedSummary, setCombinedSummary] = useState<CombinedSummary | null>(null);
  const [combinedFiles, setCombinedFiles] = useState<File[]>([]);
  const [copied, setCopied] = useState<boolean>(false);
  const [pdfFiles, setPdfFiles] = useState<File[]>([]);
  const [maxSizeKb, setMaxSizeKb] = useState<number>(495);
  const [removeColor, setRemoveColor] = useState<boolean>(true);
  const [pdfLoading, setPdfLoading] = useState<boolean>(false);
  const [pdfError, setPdfError] = useState<string | null>(null);
  const [pdfSuccess, setPdfSuccess] = useState<string | null>(null);

  const handlePdfUpload = async () => {
    if (pdfFiles.length === 0) {
      setPdfError('Будь ласка, оберіть файл');
      return;
    }

    setPdfLoading(true);
    setPdfError(null);
    setPdfSuccess(null);

    const formData = new FormData();
    for (const pdfFile of pdfFiles) {
      formData.append('files', pdfFile);
    }
    formData.append('max_size_kb', String(maxSizeKb));
    formData.append('remove_color', String(removeColor));

    try {
      const response = await fetch(`${API_BASE_URL}/api/compress-pdf`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errText = await response.text();
        throw new Error(errText || 'Помилка при стисненні PDF');
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download =
        pdfFiles.length === 1
          ? `compressed_${pdfFiles[0].name}`
          : 'compressed_pdfs.zip';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
      setPdfSuccess(
        pdfFiles.length === 1
          ? 'PDF успішно стиснуто та завантажено'
          : 'PDF-файли успішно стиснуто та завантажено',
      );
    } catch (err: unknown) {
      if (err instanceof Error) {
        setPdfError(err.message);
      } else {
        setPdfError('Невідома помилка при стисненні PDF');
      }
    } finally {
      setPdfLoading(false);
    }
  };

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setError(null);
    }
  };

  const handleUpload = async () => {
    if (!file) {
      setError('Будь ласка, оберіть файл');
      return;
    }

    setLoading(true);
    setError(null);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('parse_uktzed', String(parseUktzed));

    try {
      const response = await fetch(`${API_BASE_URL}/api/parse-invoice`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errText = await response.text();
        throw new Error(errText || 'Помилка при обробці документа');
      }

      const result: InvoiceData = await response.json();
      setData(result);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(
          err.message === 'Failed to fetch'
            ? `Не вдалося підключитися до API (${API_BASE_URL}). Перевірте API Gateway і CloudWatch.`
            : err.message
        );
      } else {
        setError('Невідома помилка');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleApplicationFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setApplicationFile(e.target.files[0]);
      setApplicationError(null);
    }
  };

  const handleApplicationUpload = async () => {
    if (!applicationFile) {
      setApplicationError('Будь ласка, оберіть файл заявки');
      return;
    }

    setApplicationLoading(true);
    setApplicationError(null);

    const formData = new FormData();
    formData.append('file', applicationFile);

    try {
      const response = await fetch(`${API_BASE_URL}/api/parse-application`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errText = await response.text();
        throw new Error(errText || 'Помилка при обробці заявки');
      }

      const result: ApplicationData = await response.json();
      setApplicationData(result);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setApplicationError(err.message);
      } else {
        setApplicationError('Невідома помилка');
      }
    } finally {
      setApplicationLoading(false);
    }
  };

  const handleCmrFileChange = (file: File | null) => {
    setCmrFile(file);
    setCmrError(null);
  };

  const handleCmrUpload = async () => {
    if (!cmrFile) {
      setCmrError('Будь ласка, оберіть файл CMR');
      return;
    }

    setCmrLoading(true);
    setCmrError(null);
    const formData = new FormData();
    formData.append('file', cmrFile);

    try {
      const response = await fetch(`${API_BASE_URL}/api/parse-cmr`, {
        method: 'POST',
        body: formData,
      });
      if (!response.ok) {
        const errText = await response.text();
        throw new Error(errText || 'Помилка при обробці CMR');
      }
      const result: CMRDocument = await response.json();
      setCmrData(result);
    } catch (err: unknown) {
      setCmrError(err instanceof Error ? err.message : 'Невідома помилка');
    } finally {
      setCmrLoading(false);
    }
  };

  const handleCombinedUpload = async () => {
    if (combinedFiles.length !== 3) {
      setCombinedError('Будь ласка, оберіть усі три файли');
      return;
    }

    setCombinedLoading(true);
    setCombinedError(null);
    const formData = new FormData();

    let invoiceCount = 0;
    let applicationCount = 0;
    let cmrCount = 0;

    for (const f of combinedFiles) {
      const fileType = identifyFileType(f.name);
      if (fileType === 'invoice') {
        formData.append('invoice_file', f);
        invoiceCount++;
      } else if (fileType === 'application') {
        formData.append('application_file', f);
        applicationCount++;
      } else if (fileType === 'cmr') {
        formData.append('cmr_file', f);
        cmrCount++;
      }
    }

    if (invoiceCount !== 1 || applicationCount !== 1 || cmrCount !== 1) {
      setCombinedError(
        'Не вдалося ідентифікувати типи файлів. Переконайтесь, що імена містять "invoice"/"інвойс", "application"/"заявка" або "cmr".',
      );
      setCombinedLoading(false);
      return;
    }

    formData.append('parse_uktzed', String(parseUktzed));

    try {
      const response = await fetch(`${API_BASE_URL}/api/parse-transport-documents`, {
        method: 'POST',
        body: formData,
      });
      if (!response.ok) {
        const errText = await response.text();
        throw new Error(errText || 'Помилка при обробці документів');
      }
      const result: CombinedDocumentData = await response.json();
      setCombinedSummary(result.summary);
      setData(result.invoice);
      setApplicationData(result.application);
      setCmrData(result.cmr);
      setError(null);
      setApplicationError(null);
      setCmrError(null);
    } catch (err: unknown) {
      setCombinedError(err instanceof Error ? err.message : 'Невідома помилка');
    } finally {
      setCombinedLoading(false);
    }
  };

  const downloadExcel = async () => {
    if (!data) return;

    try {
      const response = await fetch(`${API_BASE_URL}/api/export-excel`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });

      if (!response.ok) {
        const errText = await response.text();
        throw new Error(`HTTP ${response.status}: ${errText}`);
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `Invoice_${data.invoice_number || 'export'}.xlsx`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(`Не вдалося завантажити Excel: ${err.message}`);
      } else {
        setError('Невідома помилка при завантаженні Excel');
      }
    }
  };

  const copyCombinedToClipboard = async () => {
    if (!combinedSummary) return;

    const val = (v: unknown): string =>
      v === null || v === undefined || v === '' ? '-' : String(v);

    const row = [
      val(combinedSummary.contract),
      val(""),
      val(combinedSummary.net_weight_kg),
      val(combinedSummary.border_crossing_point),
      val(combinedSummary.carrier),
      val(combinedSummary.nomenclature.join(', ')),
      val(combinedSummary.unloading_city),
      val(""),
      val(combinedSummary.vehicle_number),
    ].join('\t');

    try {
      await navigator.clipboard.writeText(row);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy to clipboard:', err);
      setError('Не вдалося скопіювати в буфер обміну');
    }
  };

  return (
    <div className="min-h-screen bg-gray-100 p-8">
      <div className="max-w-7xl mx-auto">
        <h1 className="text-3xl font-bold mb-6 text-gray-800">
          Завантажте файли для обробки.
        </h1>

        <div className="flex flex-col lg:flex-row gap-6 mb-8">
          <div className="bg-white p-6 rounded-lg shadow-md flex-1">
            <label className="block text-gray-700 font-semibold mb-2">
              Завантажте PDF-файл для стиснення:
            </label>
            <div className="flex flex-col gap-4">
              <div className="flex gap-4 items-center">
                <FilePicker
                  label="Обрати PDF-файли"
                  accept="application/pdf"
                  multiple
                  onChange={(files) => {
                    setPdfFiles(files ?? []);
                    setPdfError(null);
                    setPdfSuccess(null);
                  }}
                  selectedFile={pdfFiles}
                  disabled={pdfLoading}
                />
              </div>
              <div>
                <label className="block text-gray-700 font-semibold mb-2">
                  Макс. розмір (KB):
                </label>
                <input
                  type="number"
                  value={maxSizeKb}
                  onChange={(e) => setMaxSizeKb(Number(e.target.value))}
                  min="1"
                  className="border p-2 rounded w-32"
                />
              </div>
              <label className="flex items-center gap-2 text-gray-700 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={removeColor}
                  onChange={(e) => setRemoveColor(e.target.checked)}
                  className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                <span className="font-semibold">Remove color</span>
              </label>
              <button
                onClick={handlePdfUpload}
                disabled={pdfLoading}
                className="mt-4 w-48 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white font-bold px-6 py-2 rounded transition-colors"
              >
                {pdfLoading ? 'Стиснення...' : 'Стиснути'}
              </button>
            </div>
            {pdfLoading && (
              <div className="mt-4 text-blue-600 font-semibold">
                Стиснення PDF...
              </div>
            )}
            {pdfError && (
              <div className="mt-4 text-red-600 font-semibold">
                {pdfError}
              </div>
            )}
            {pdfSuccess && (
              <div className="mt-4 text-green-600 font-semibold">
                {pdfSuccess}
              </div>
            )}
          </div>

          <div className="bg-white p-6 rounded-lg shadow-md flex-1">
            <h2 className="text-2xl font-bold mb-4 text-gray-800">
              Обробити комплект документів
            </h2>
            <p className="mb-4 text-gray-600">
              Завантажте інвойс, транспортну заявку та CMR одним запитом.
            </p>
            <div className="flex flex-col gap-4">
              <label className="font-semibold text-gray-700">
                Документи (3 файли)
                <div className="flex items-center gap-2 mt-1">
                  <input
                    type="file"
                    accept="application/pdf,image/jpeg,image/png,image/webp,image/bmp,image/tiff"
                    multiple
                    id="combined-file-input"
                    onChange={(e) => {
                      const chosen = Array.from(e.target.files ?? []).slice(0, 3);
                      setCombinedFiles(chosen);
                      setCombinedError(null);
                    }}
                    disabled={combinedLoading}
                    className="hidden"
                  />
                  <label
                    htmlFor="combined-file-input"
                    className={`inline-block ${combinedLoading ? 'bg-gray-100 cursor-not-allowed' : 'bg-gray-200 hover:bg-gray-300'} text-gray-800 font-semibold px-4 py-2 rounded transition-colors`}
                  >
                    Обрати 3 файли
                  </label>
                  <span className="text-sm text-gray-600 truncate">
                    {combinedFiles.length > 0
                      ? `${combinedFiles.length} файлів обрано`
                      : 'Файли не обрано'}
                  </span>
                </div>
                {combinedFiles.length > 0 && (
                  <div className="mt-2 space-y-0.5">
                    {combinedFiles.map((f, i) => (
                      <div key={i} className="text-sm text-gray-600">
                        {f.name}
                      </div>
                    ))}
                  </div>
                )}
              </label>
            </div>
            <button
              type="button"
              onClick={handleCombinedUpload}
              disabled={combinedLoading}
              className="mt-4 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white font-bold px-6 py-2 rounded transition-colors"
            >
              {combinedLoading ? 'Обробка трьох документів...' : 'Обробити комплект'}
            </button>
            {combinedLoading && <div className="mt-4 text-blue-600 font-semibold">Розпізнавання документів...</div>}
            {combinedError && <div className="mt-4 text-red-600 font-semibold">{combinedError}</div>}
          </div>
        </div>

        {combinedSummary && (
          <div className="bg-white p-6 rounded-lg shadow-md mb-8">
            <h2 className="text-2xl font-bold mb-4 text-gray-800">Зведені дані документів</h2>
            <button
              onClick={copyCombinedToClipboard}
              className="bg-green-600 hover:bg-green-700 text-white font-bold px-4 py-2 rounded transition-colors text-sm"
            >
              {copied ? '✅ Скопійовано!' : '📋 Копіювати в Google Sheets'}
            </button>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div><span className="font-bold">Контракт:</span> {combinedSummary.contract || '-'}</div>
              <div><span className="font-bold">Маса нетто, кг:</span> {combinedSummary.net_weight_kg ?? '-'}</div>
              <div><span className="font-bold">ПП:</span> {combinedSummary.border_crossing_point || '-'}</div>
              <div><span className="font-bold">Перевізник:</span> {combinedSummary.carrier || '-'}</div>
              <div className="md:col-span-2"><span className="font-bold">Номенклатура:</span> {combinedSummary.nomenclature.join(', ') || '-'}</div>
              <div><span className="font-bold">Місто розвантаження:</span> {combinedSummary.unloading_city || '-'}</div>
              <div><span className="font-bold">ВН номер (ПД):</span> {combinedSummary.vn_number_pd || '-'}</div>
              <div><span className="font-bold">Номер машини:</span> {combinedSummary.vehicle_number || '-'}</div>
              <div><span className="font-bold">ПД:</span> {combinedSummary.tax_document_number || '-'}</div>
            </div>
          </div>
        )}

        {/* Форма завантаження інвойсу */}
        <div className="bg-white p-6 rounded-lg shadow-md mb-8">
          <label className="block text-gray-700 font-semibold mb-2">
            Завантажте файл інвойсу:
          </label>
          <div className="flex gap-4 items-center">
            <FilePicker
              label="Обрати PDF"
              accept="application/pdf,image/jpeg,image/png,image/webp,image/bmp,image/tiff"
              onChange={setFile}
              selectedFile={file}
              disabled={loading}
            />
            <button
              onClick={handleUpload}
              disabled={loading}
              className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white font-bold px-6 py-2 rounded transition-colors"
            >
              {loading ? 'Обробка...' : 'Обробити'}
            </button>
          </div>

          <label className="mt-4 flex items-center gap-2 text-gray-700 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={parseUktzed}
              onChange={(e) => setParseUktzed(e.target.checked)}
              className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            <span className="font-semibold">
              Підбирати коди УКТ ЗЕД за допомогою AI
            </span>
          </label>

          {loading && (
            <div className="mt-4 text-blue-600 font-semibold">
              {parseUktzed
                ? 'Обробка документа та пошук кодів УКТ ЗЕД...'
                : 'Обробка документа...'}
            </div>
          )}

          {error && (
            <div className="mt-4 text-red-600 font-semibold">
              {error}
            </div>
          )}
        </div>

        {/* Заголовок інвойсу */}
        {data && (
          <div className="bg-white p-6 rounded-lg shadow-md mb-8 grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <span className="font-bold">№ Інвойсу:</span>{' '}
              {data.invoice_number || '-'}
            </div>
            <div>
              <span className="font-bold">Дата:</span>{' '}
              {data.invoice_date || '-'}
            </div>
            <div>
              <span className="font-bold">Валюта:</span>{' '}
              {data.currency || '-'}
            </div>
            <div>
              <span className="font-bold">Продавець:</span>{' '}
              {data.seller_name || '-'}
            </div>
            <div>
              <span className="font-bold">Покупець:</span>{' '}
              {data.buyer_name || '-'}
            </div>
            <div>
              <span className="font-bold">Загальна сума:</span>{' '}
              {data.total_invoice_amount ?? '-'}
            </div>
          </div>
        )}

        {/* Кнопка завантаження Excel */}
        {/* {data && (
          <div className="mb-8">
            <button
              onClick={downloadExcel}
              className="bg-green-600 hover:bg-green-700 text-white font-bold px-6 py-2 rounded transition-colors"
            >
              📥 Завантажити Excel
            </button>
          </div>
        )} */}

        {/* Таблиця товарів */}
        {data && data.items && data.items.length > 0 && (
          <div className="bg-white p-6 rounded-lg shadow-md mb-8">
            <h2 className="text-xl font-bold mb-4">
              Товари та підказки УКТ ЗЕД
            </h2>
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-gray-800 text-white">
                    <th className="p-3">№</th>
                    <th className="p-3">Артикул</th>
                    <th className="p-3">Опис товару</th>
                    <th className="p-3">К-сть</th>
                    <th className="p-3">Од.</th>
                    <th className="p-3">Ціна</th>
                    <th className="p-3">Сума</th>
                    <th className="p-3 text-blue-300">Код УКТ ЗЕД (AI)</th>
                    <th className="p-3 text-blue-300">Обґрунтування</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((item, index) => {
                    const codeInfo = item.uktzed_suggestion;
                    return (
                      <tr key={index} className="border-b hover:bg-gray-50">
                        <td className="p-3">{item.item_number ?? index + 1}</td>
                        <td className="p-3">{item.article || '-'}</td>
                        <td className="p-3 font-medium">{item.description}</td>
                        <td className="p-3">{item.quantity}</td>
                        <td className="p-3">{item.unit}</td>
                        <td className="p-3">{item.price_per_unit}</td>
                        <td className="p-3">{item.total_amount}</td>
                        <td className="p-3 bg-blue-50 font-bold text-blue-800">
                          {codeInfo?.code || '-'}
                        </td>
                        <td className="p-3 bg-blue-50 text-xs text-gray-600">
                          <div className="font-semibold text-gray-800">
                            {codeInfo?.description || ''}
                          </div>
                          <div>{codeInfo?.justification || ''}</div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Форма завантаження заявки */}
        <div className="bg-white p-6 rounded-lg shadow-md mb-8">
          <label className="block text-gray-700 font-semibold mb-2">
            Завантажте файл транспортної заявки:
          </label>
          <div className="flex gap-4 items-center">
            <FilePicker
              label="Обрати PDF"
              accept="application/pdf,image/jpeg,image/png,image/webp,image/bmp,image/tiff"
              onChange={setApplicationFile}
              selectedFile={applicationFile}
              disabled={applicationLoading}
            />
            <button
              onClick={handleApplicationUpload}
              disabled={applicationLoading}
              className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white font-bold px-6 py-2 rounded transition-colors"
            >
              {applicationLoading ? 'Обробка...' : 'Обробити'}
            </button>
          </div>

          {applicationLoading && (
            <div className="mt-4 text-blue-600 font-semibold">
              Обробка транспортної заявки...
            </div>
          )}

          {applicationError && (
            <div className="mt-4 text-red-600 font-semibold">
              {applicationError}
            </div>
          )}
        </div>

        {/* Результати заявки */}
        {applicationData && (
          <div className="bg-white p-6 rounded-lg shadow-md mb-8 grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <span className="font-bold">№ Заявки:</span>{' '}
              {applicationData.application_number || '-'}
            </div>
            <div>
              <span className="font-bold">Дата заявки:</span>{' '}
              {applicationData.application_date || '-'}
            </div>
            <div>
              <span className="font-bold">№ Договору:</span>{' '}
              {applicationData.contract_number || '-'}
            </div>
            <div>
              <span className="font-bold">Дата договору:</span>{' '}
              {applicationData.contract_date || '-'}
            </div>
            <div>
              <span className="font-bold">Вид перевезення:</span>{' '}
              {applicationData.transport_type || '-'}
            </div>
            <div>
              <span className="font-bold">Маршрут:</span>{' '}
              {applicationData.route || '-'}
            </div>
            <div className="md:col-span-3">
              <span className="font-bold">Вантажовідправник:</span>{' '}
              {applicationData.shipper || '-'}
            </div>
            <div className="md:col-span-3">
              <span className="font-bold">Адреса завантаження:</span>{' '}
              {applicationData.loading_address || '-'}
            </div>
            <div>
              <span className="font-bold">Дата/час завантаження:</span>{' '}
              {applicationData.loading_datetime || '-'}
            </div>
            <div className="md:col-span-3">
              <span className="font-bold">Вантаж (найменування, пакування):</span>{' '}
              {applicationData.cargo_name_and_packaging || '-'}
            </div>
            <div className="md:col-span-3">
              <span className="font-bold">Кількість/габарити/вага:</span>{' '}
              {applicationData.cargo_quantity_and_dimensions || '-'}
            </div>
            <div className="md:col-span-3">
              <span className="font-bold">Адреса замитнення:</span>{' '}
              {applicationData.customs_outbound_address || '-'}
            </div>
            <div>
              <span className="font-bold">Пункт перетину кордону:</span>{' '}
              {applicationData.border_crossing_point || '-'}
            </div>
            <div className="md:col-span-3">
              <span className="font-bold">Адреса розмитнення:</span>{' '}
              {applicationData.customs_inbound_address || '-'}
            </div>
            <div className="md:col-span-3">
              <span className="font-bold">Адреса розвантаження:</span>{' '}
              {applicationData.unloading_address || '-'}
            </div>
            <div>
              <span className="font-bold">Дата/час розвантаження:</span>{' '}
              {applicationData.unloading_datetime || '-'}
            </div>
            <div className="md:col-span-3">
              <span className="font-bold">Вимоги до ТЗ:</span>{' '}
              {applicationData.vehicle_requirements || '-'}
            </div>
            <div className="md:col-span-3">
              <span className="font-bold">Транспортний засіб:</span>{' '}
              {applicationData.vehicle_info || '-'}
            </div>
            <div className="md:col-span-3">
              <span className="font-bold">Водій:</span>{' '}
              {applicationData.driver_info || '-'}
            </div>
            <div className="md:col-span-3">
              <span className="font-bold">Відповідальна особа Замовника:</span>{' '}
              {applicationData.customer_responsible_person || '-'}
            </div>
            <div className="md:col-span-3">
              <span className="font-bold">Ціна та умови:</span>{' '}
              {applicationData.price_terms || '-'}
            </div>
          </div>
        )}

        <div className="bg-white p-6 rounded-lg shadow-md mb-8">
          <label className="block text-gray-700 font-semibold mb-2">
            Завантажте файл CMR для обробки:
          </label>
          <div className="flex gap-4 items-center">
            <FilePicker
              label="Обрати PDF"
              accept="application/pdf,image/jpeg,image/png,image/webp,image/bmp,image/tiff"
              onChange={handleCmrFileChange}
              selectedFile={cmrFile}
              disabled={cmrLoading}
            />
            <button
              onClick={handleCmrUpload}
              disabled={cmrLoading}
              className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white font-bold px-6 py-2 rounded transition-colors"
            >
              {cmrLoading ? 'Обробка...' : 'Обробити'}
            </button>
          </div>
          {cmrLoading && (
            <div className="mt-4 text-blue-600 font-semibold">
              Обробка CMR...
            </div>
          )}
          {cmrError && <div className="mt-4 text-red-600 font-semibold">{cmrError}</div>}
        </div>

        {cmrData && (
          <div className="bg-white p-6 rounded-lg shadow-md mb-8">
            <h2 className="text-2xl font-bold mb-4 text-gray-800">Результати CMR</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div><span className="font-bold">№ CMR:</span> {cmrData.cmr_number || '-'}</div>
              <div><span className="font-bold">Номер дорожнього листа:</span> {cmrData.waybill_number || '-'}</div>
              <div><span className="font-bold">Відправник:</span> {cmrData.consignor?.name_and_address || '-'} ({cmrData.consignor?.tax_id || 'ІПН не вказано'})</div>
              <div><span className="font-bold">Одержувач:</span> {cmrData.consignee?.name_and_address || '-'} ({cmrData.consignee?.tax_id || 'ІПН не вказано'})</div>
              <div><span className="font-bold">Місце завантаження:</span> {cmrData.taking_over_place || '-'}</div>
              <div><span className="font-bold">Місце доставки:</span> {cmrData.delivery_place || '-'}</div>
              <div><span className="font-bold">Перевізник:</span> {cmrData.carrier?.name_and_address || '-'} ({cmrData.carrier?.tax_id || 'ІПН не вказано'})</div>
              <div><span className="font-bold">Наступний перевізник:</span> {cmrData.successive_carriers?.name_and_address || '-'} ({cmrData.successive_carriers?.tax_id || 'ІПН не вказано'})</div>
              <div><span className="font-bold">Додані документи:</span> {cmrData.annexed_documents || '-'}</div>
              <div><span className="font-bold">Інструкції відправника:</span> {cmrData.senders_instructions || '-'}</div>
              <div><span className="font-bold">Умови оплати:</span> {cmrData.freight_payment_instructions || '-'}</div>
              <div><span className="font-bold">Спеціальні умови:</span> {cmrData.special_agreements || '-'}</div>
              <div><span className="font-bold">Застереження перевізника:</span> {cmrData.carriers_reservations || '-'}</div>
              <div><span className="font-bold">Водії:</span> {cmrData.drivers_names || '-'}</div>
              <div><span className="font-bold">Місце складання:</span> {cmrData.established_in_place || '-'}</div>
              <div><span className="font-bold">Дата складання:</span> {cmrData.established_in_date || '-'}</div>
              <div><span className="font-bold">Дата отримання вантажу:</span> {cmrData.goods_received_date || '-'}</div>
              <div><span className="font-bold">Підпис та печатка:</span> {cmrData.consignee_signature_and_stamp || '-'}</div>
              <div><span className="font-bold">Автомобіль:</span> {cmrData.vehicle_info?.tractor_registration || '-'} ({cmrData.vehicle_info?.tractor_brand || '-'})</div>
              <div><span className="font-bold">Причіп:</span> {cmrData.vehicle_info?.trailer_registration || '-'} ({cmrData.vehicle_info?.trailer_brand || '-'})</div>
              <div><span className="font-bold">Прибуття на завантаження:</span> {cmrData.arrival_to_loading_time || '-'}</div>
              <div><span className="font-bold">Виїзд із завантаження:</span> {cmrData.departure_from_loading_time || '-'}</div>
              <div><span className="font-bold">Прибуття на розвантаження:</span> {cmrData.arrival_to_unloading_time || '-'}</div>
              <div><span className="font-bold">Виїзд із розвантаження:</span> {cmrData.departure_from_unloading_time || '-'}</div>
            </div>
            {cmrData.cargo_items.length > 0 && (
              <div className="overflow-x-auto mt-6">
                <h3 className="text-xl font-bold mb-3">Вантаж</h3>
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="bg-gray-800 text-white">
                      <th className="p-3">Знаки та номери</th>
                      <th className="p-3">Місця</th>
                      <th className="p-3">Пакування</th>
                      <th className="p-3">Найменування</th>
                      <th className="p-3">Стат. №</th>
                      <th className="p-3">Брутто, кг</th>
                      <th className="p-3">Обсяг, м³</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cmrData.cargo_items.map((item, index) => (
                      <tr key={index} className="border-b hover:bg-gray-50">
                        <td className="p-3">{item.marks_and_numbers || '-'}</td>
                        <td className="p-3">{item.number_of_packs || '-'}</td>
                        <td className="p-3">{item.type_of_packing || '-'}</td>
                        <td className="p-3 font-medium">{item.name_of_goods || '-'}</td>
                        <td className="p-3">{item.statistic_number || '-'}</td>
                        <td className="p-3">{item.gross_weight_kg ?? '-'}</td>
                        <td className="p-3">{item.volume_m3 ?? '-'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
