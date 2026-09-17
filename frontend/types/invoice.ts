export interface UktZedSuggestion {
  code: string;
  description: string;
  justification: string;
}

export interface InvoiceItem {
  item_number?: number | null;
  article?: string | null;
  description: string;
  quantity: number;
  unit: string;
  price_per_unit: number;
  total_amount: number;
  country_of_origin?: string | null;
  net_weight_kg?: number | null;
  uktzed_suggestion?: UktZedSuggestion | null;
}

export interface InvoiceData {
  invoice_number?: string | null;
  invoice_date?: string | null;
  currency?: string | null;
  seller_name?: string | null;
  buyer_name?: string | null;
  total_invoice_amount?: number | null;
  items: InvoiceItem[];
}