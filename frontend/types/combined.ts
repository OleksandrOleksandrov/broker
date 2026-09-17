export interface CombinedSummary {
  contract?: string | null;
  net_weight_kg?: number | null;
  border_crossing_point?: string | null;
  carrier?: string | null;
  nomenclature: string[];
  unloading_city?: string | null;
  invoice_number?: string | null;
  vn_number_pd?: string | null;
  vehicle_number?: string | null;
  tax_document_number?: string | null;
}

export interface CombinedDocumentData {
  summary: CombinedSummary;
  invoice: import('./invoice').InvoiceData;
  application: import('./application').ApplicationData;
  cmr: import('./cmr').CMRDocument;
}