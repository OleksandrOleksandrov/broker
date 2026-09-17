export interface CMRParty {
  name_and_address?: string | null;
  tax_id?: string | null;
}

export interface CMRCargoItem {
  marks_and_numbers?: string | null;
  number_of_packs?: string | null;
  type_of_packing?: string | null;
  name_of_goods?: string | null;
  statistic_number?: string | null;
  gross_weight_kg?: number | null;
  volume_m3?: number | null;
}

export interface CMRVehicle {
  tractor_registration?: string | null;
  trailer_registration?: string | null;
  tractor_brand?: string | null;
  trailer_brand?: string | null;
}

export interface CMRDocument {
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