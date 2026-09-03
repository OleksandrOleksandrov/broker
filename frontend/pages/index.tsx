import React, { useState, ChangeEvent } from 'react';

const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
).replace(/\/$/, '');

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

interface ApplicationData {
  application_number?: string | null;
  application_date?: string | null;
  contract_number?: string | null;
  contract_date?: string | null;
  transport_type?: string | null;
  route?: string | null;
  shipper?: string | null;
  loading_address?: string | null;
  loading_datetime?: string | null;
  cargo_name_and_packaging?: string | null;
  cargo_quantity_and_dimensions?: string | null;
  customs_outbound_address?: string | null;
  border_crossing_point?: string | null;
  customs_inbound_address?: string | null;
  unloading_address?: string | null;
  unloading_datetime?: string | null;
  vehicle_requirements?: string | null;
  vehicle_info?: string | null;
  driver_info?: string | null;
  customer_responsible_person?: string | null;
  price_terms?: string | null;
}

interface CMRParty {
  name_and_address?: string | null;
  tax_id?: string | null;
}

interface CMRCargoItem {
  marks_and_numbers?: string | null;
  number_of_packs?: string | null;
  type_of_packing?: string | null;
  name_of_goods?: string | null;
  statistic_number?: string | null;
  gross_weight_kg?: number | null;
  volume_m3?: number | null;
}

interface CMRVehicle {
  tractor_registration?: string | null;
  trailer_registration?: string | null;
  tractor_brand?: string | null;
  trailer_brand?: string | null;
}

interface CMRDocument {
  cmr_number?: string | null;
  consignor?: CMRParty | null;
  consignee?: CMRParty | null;
  delivery_place?: string | null;
  taking_over_place?: string | null;
  annexed_documents?: string | null;
  cargo_items: CMRCargoItem[];
  senders_instructions?: string | null;
  carrier?: CMRParty | null;
  successive_carriers?: CMRParty | null;
  carriers_reservations?: string | null;
  freight_payment_instructions?: string | null;
  special_agreements?: string | null;
  established_in_place?: string | null;
  established_in_date?: string | null;
  arrival_to_loading_time?: string | null;
  departure_from_loading_time?: string | null;
  waybill_number?: string | null;
  drivers_names?: string | null;
  goods_received_date?: string | null;
  arrival_to_unloading_time?: string | null;
  departure_from_unloading_time?: string | null;
  vehicle_info?: CMRVehicle | null;
  consignee_signature_and_stamp?: string | null;
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
        setError(err.message);
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
      setApplicationError('Будь ласка, оберіть PDF-файл заявки');
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

  const handleCmrFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setCmrFile(e.target.files[0]);
      setCmrError(null);
    }
  };

  const handleCmrUpload = async () => {
    if (!cmrFile) {
      setCmrError('Будь ласка, оберіть PDF-файл CMR');
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

  return (
    <div className="min-h-screen bg-gray-100 p-8">
      <div className="max-w-7xl mx-auto">
        <h1 className="text-3xl font-bold mb-6 text-gray-800">
          Завантажте PDF-інвойс для обробки та отримання кодів УКТ ЗЕД
        </h1>

        {/* Форма завантаження інвойсу */}
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
          <h2 className="text-2xl font-bold mb-4 text-gray-800">
            Завантажте транспортну заявку для обробки
          </h2>
          <label className="block text-gray-700 font-semibold mb-2">
            Завантажте PDF-заявку:
          </label>
          <div className="flex gap-4">
            <input
              type="file"
              accept="application/pdf"
              onChange={handleApplicationFileChange}
              className="border p-2 rounded w-full"
            />
            <button
              onClick={handleApplicationUpload}
              disabled={applicationLoading}
              className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white font-bold px-6 py-2 rounded transition-colors"
            >
              {applicationLoading ? 'Обробка...' : 'Обробити заявку'}
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
          <h2 className="text-2xl font-bold mb-4 text-gray-800">
            Завантажте CMR для обробки
          </h2>
          <div className="flex gap-4">
            <input
              type="file"
              accept="application/pdf"
              onChange={handleCmrFileChange}
              className="border p-2 rounded w-full"
            />
            <button
              onClick={handleCmrUpload}
              disabled={cmrLoading}
              className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white font-bold px-6 py-2 rounded transition-colors"
            >
              {cmrLoading ? 'Обробка...' : 'Обробити CMR'}
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
