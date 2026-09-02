import React, { useState, ChangeEvent } from 'react';

// 1. Інтерфейси TypeScript для строгої типізації даних
interface UktZedSuggestion {
  code: string;
  description: string;
  justification: string;
}

interface InvoiceItem {
  item_number?: number | null;
  article?: string | null;
  description: string;
  quantity: number;
  unit: string;
  price_per_unit: number;
  total_amount: number;
  country_of_origin?: string | null;
  uktzed_suggestion?: UktZedSuggestion | null;
}

interface InvoiceData {
  invoice_number?: string | null;
  invoice_date?: string | null;
  currency?: string | null;
  seller_name?: string | null;
  buyer_name?: string | null;
  total_invoice_amount?: number | null;
  items: InvoiceItem[];
}

export default function InvoiceParserApp(): React.JSX.Element {
  // 2. Стейт компонента
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [data, setData] = useState<InvoiceData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [parseUktzed, setParseUktzed] = useState<boolean>(false);

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setError(null);
    }
  };

  const handleUpload = async () => {
    if (!file) {
      setError('Будь ласка, оберіть PDF-файл');
      return;
    }

    setLoading(true);
    setError(null);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('parse_uktzed', String(parseUktzed));

    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/parse-invoice`, {
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
        setError(err.message);
      } else {
        setError('Невідома помилка');
      }
    } finally {
      setLoading(false);
    }
  };

  const downloadExcel = async () => {
    if (!data) return;

    const apiUrl = process.env.NEXT_PUBLIC_API_URL;
    if (!apiUrl) {
      setError('API_URL не задано');
      return;
    }

    try {
      const response = await fetch(`${apiUrl}/api/export-excel`, {
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

  return (
    <div className="min-h-screen bg-gray-100 p-8">
      <div className="max-w-7xl mx-auto">
        <h1 className="text-3xl font-bold mb-6 text-gray-800">
          Завантажте PDF-інвойс для обробки та отримання кодів УКТ ЗЕД
        </h1>

        {/* Форма завантаження */}
        <div className="bg-white p-6 rounded-lg shadow-md mb-8">
          <label className="block text-gray-700 font-semibold mb-2">
            Завантажте PDF-інвойс:
          </label>
          <div className="flex gap-4">
            <input
              type="file"
              accept="application/pdf"
              onChange={handleFileChange}
              className="border p-2 rounded w-full"
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
          <div className="bg-white p-6 rounded-lg shadow-md">
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
      </div>
    </div>
  );
}
