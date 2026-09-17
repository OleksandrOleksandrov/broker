from typing import List, Optional

from pydantic import BaseModel, Field


class CMRParty(BaseModel):
    name_and_address: Optional[str] = Field(
        default=None,
        description="Nosaukums, adrese, valsts / Name, address, state[span_0](start_span)[span_0](end_span)",
    )
    tax_id: Optional[str] = Field(
        default=None,
        description="Tax or VAT ID, e.g., SELCUK V.D.[span_1](start_span)[span_1](end_span)",
    )


class CMRCargoItem(BaseModel):
    marks_and_numbers: Optional[str] = Field(
        default=None,
        description="6 Zīmes un numuri / Marks and numbers[span_2](start_span)[span_2](end_span)",
    )
    number_of_packs: Optional[str] = Field(
        default=None,
        description="7 Vietu skaits / Number of packs[span_3](start_span)[span_3](end_span)",
    )
    type_of_packing: Optional[str] = Field(
        default=None,
        description="8 Iepakojuma veids / Type of packing[span_4](start_span)[span_4](end_span)",
    )
    name_of_goods: Optional[str] = Field(
        default=None,
        description="9 Kravas nosaukums / Name of the goods[span_5](start_span)[span_5](end_span)",
    )
    statistic_number: Optional[str] = Field(
        default=None,
        description="10 Statist.Nr. / Statistic.Nr.[span_6](start_span)[span_6](end_span)",
    )
    gross_weight_kg: Optional[float] = Field(
        default=None,
        description="11 Bruto svars / Brutto weight in (kg)[span_7](start_span)[span_7](end_span)",
    )
    volume_m3: Optional[float] = Field(
        default=None,
        description="12 Apjoms (m3) / Volume in (m3)[span_8](start_span)[span_8](end_span)",
    )


class CMRVehicle(BaseModel):
    tractor_registration: Optional[str] = Field(
        default=None,
        description="25 Registr Nr. Vilcējs/Car[span_9](start_span)[span_9](end_span)",
    )
    trailer_registration: Optional[str] = Field(
        default=None,
        description="25 Registr Nr. Puspiekabe/Sidecar[span_10](start_span)[span_10](end_span)",
    )
    tractor_brand: Optional[str] = Field(
        default=None,
        description="26 Marka/type Vilcējs/Car[span_11](start_span)[span_11](end_span)",
    )
    trailer_brand: Optional[str] = Field(
        default=None,
        description="26 Marka/type Puspiekabe/Sidecar[span_12](start_span)[span_12](end_span)",
    )


class CMRDocument(BaseModel):
    cmr_number: Optional[str] = Field(
        default=None,
        description="CMR Number (e.g., TR 10-05/2025)[span_13](start_span)[span_13](end_span)",
    )
    consignor: Optional[CMRParty] = Field(
        default=None,
        description="1 Nosūtītājs / Consignor[span_14](start_span)[span_14](end_span)",
    )
    consignee: Optional[CMRParty] = Field(
        default=None,
        description="2 Saņēmējs / Consignee[span_15](start_span)[span_15](end_span)",
    )
    delivery_place: Optional[str] = Field(
        default=None,
        description="3 Kravas izkraušanas vieta / Place of delivery of the goods[span_16](start_span)[span_16](end_span)",
    )
    delivery_city: Optional[str] = Field(
        default=None,
        description="3 Kravas izkraušanas vieta / Place of delivery of the goods. Take only the city name from the full address, e.g., 'Rīga' or 'Riga'.",
    )
    taking_over_place: Optional[str] = Field(
        default=None,
        description="4 Kravas iekraušanas vieta un datums / Place and date of taking over of the goods[span_17](start_span)[span_17](end_span)",
    )
    annexed_documents: Optional[str] = Field(
        default=None,
        description="5 Pievienotie dokumenti / Annexed documents Locate the invoice number. To prevent tokenization errors with repeated zeros,"
        "transcribe the number exactly as it appears, separating every single character"
        "with a hyphen (e.g., A-C-Z-1-0-1-1-0-0-0-0-0-0-1-1-1). Count the characters to"
        "verify it is exactly 16 characters long."
        "number on a new line. If not found, write 'not found'.",
    )
    cargo_items: Optional[List[CMRCargoItem]] = Field(
        default_factory=list,
        description="Cargo details table (Fields 6-12)[span_19](start_span)[span_19](end_span)",
    )
    senders_instructions: Optional[str] = Field(
        default=None,
        description="13 Nosūtītāja norādijumi / Sender's instructions (Customs and other formalitis)[span_20](start_span)[span_20](end_span)",
    )
    carrier: Optional[CMRParty] = Field(
        default=None,
        description="16 Pārvadātājs / Carrier/forwarder[span_21](start_span)[span_21](end_span)",
    )
    successive_carriers: Optional[CMRParty] = Field(
        default=None,
        description="17 Turpmakais pārvadātājs / Successive carriers[span_22](start_span)[span_22](end_span)",
    )
    carriers_reservations: Optional[str] = Field(
        default=None,
        description="18 Pārvadātāja aizradījumi un piezīmes / Carrier's reservations and observation[span_23](start_span)[span_23](end_span)",
    )
    freight_payment_instructions: Optional[str] = Field(
        default=None,
        description="15 Apmaksas noteikumi / Directions and freight payment[span_24](start_span)[span_24](end_span)",
    )
    special_agreements: Optional[str] = Field(
        default=None,
        description="20 Īpaši saskaņoti noteikumi / Special agreements[span_25](start_span)[span_25](end_span)",
    )
    established_in_place: Optional[str] = Field(
        default=None,
        description="21 Sastādīts / Established in[span_26](start_span)[span_26](end_span)",
    )
    established_in_date: Optional[str] = Field(
        default=None,
        description="21 Datums / Date of establishment[span_27](start_span)[span_27](end_span)",
    )
    arrival_to_loading_time: Optional[str] = Field(
        default=None,
        description="22 Ierašanās iekraušanai / Arrival to loading time[span_28](start_span)[span_28](end_span)",
    )
    departure_from_loading_time: Optional[str] = Field(
        default=None,
        description="22 Aizbraukšana / Departure time[span_29](start_span)[span_29](end_span)",
    )
    waybill_number: Optional[str] = Field(
        default=None,
        description="23 Ceļazīme Nr. / Waybill Nr.[span_30](start_span)[span_30](end_span)",
    )
    drivers_names: Optional[str] = Field(
        default=None,
        description="23 Vadītāju uzvārdi / Drivers names[span_31](start_span)[span_31](end_span)",
    )
    goods_received_date: Optional[str] = Field(
        default=None,
        description="24 Krava saņemta Datums / Goods received Date[span_32](start_span)[span_32](end_span)",
    )
    arrival_to_unloading_time: Optional[str] = Field(
        default=None,
        description="24 Ierašanās iekraušanai / Arrival to unloading time[span_33](start_span)[span_33](end_span)",
    )
    departure_from_unloading_time: Optional[str] = Field(
        default=None,
        description="24 Aizbraukšana / Departure time from unloading[span_34](start_span)[span_34](end_span)",
    )
    vehicle_info: Optional[CMRVehicle] = Field(
        default=None,
        description="25-26 Vehicle registration and type information[span_35](start_span)[span_35](end_span)",
    )
    consignee_signature_and_stamp: Optional[str] = Field(
        default=None,
        description="24 Saņēmēja paraksts un zīmogs / Signature and stamp of the consignee block text[span_36](start_span)[span_36](end_span)",
    )
