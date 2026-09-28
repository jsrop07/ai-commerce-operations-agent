import type {
  ApiEnvelope,
  ReservationRiskItem,
  ReservationSourceClassification,
  ReservationValueState,
  RiskLevel,
} from "../types/contracts";

const useRealBackend =
  import.meta.env.VITE_USE_REAL_BACKEND === "true";

const backendBaseUrl =
  import.meta.env.VITE_BACKEND_BASE_URL ?? "";

const sourceClassifications: ReservationSourceClassification[] = [
  "SANITIZED_REAL",
  "FIXTURE",
  "CONTRACT_ONLY",
  "BLOCKED",
];

const valueStates: ReservationValueState[] = [
  "KNOWN",
  "UNKNOWN",
  "BLOCKED",
];

const riskLevels: RiskLevel[] = [
  "LOW",
  "MEDIUM",
  "HIGH",
];

function isRecord(
  value: unknown,
): value is Record<string, unknown> {
  return (
    typeof value === "object" &&
    value !== null &&
    !Array.isArray(value)
  );
}

async function realApiGet(
  path: string,
  signal?: AbortSignal,
): Promise<unknown> {
  const response = await fetch(
    `${backendBaseUrl}${path}`,
    {
      method: "GET",
      headers: {
        Accept: "application/json",
      },
      signal,
    },
  );

  if (!response.ok) {
    throw new Error(
      `Backend request failed: ${response.status}`,
    );
  }

  return response.json();
}

function parseNullableNumber(
  value: unknown,
  fieldName: string,
): number | null {
  if (value === null) {
    return null;
  }

  if (typeof value !== "number") {
    throw new Error(
      `Reservation field ${fieldName} is malformed`,
    );
  }

  return value;
}

function parseOptionalValueState(
  value: unknown,
): ReservationValueState | undefined {
  if (value === undefined) {
    return undefined;
  }

  if (
    typeof value === "string" &&
    valueStates.includes(
      value as ReservationValueState,
    )
  ) {
    return value as ReservationValueState;
  }

  throw new Error(
    "Reservation value state is malformed",
  );
}

function parseReservationRiskItem(
  value: unknown,
): ReservationRiskItem {
  if (
    !isRecord(value) ||
    typeof value.reservation_id !== "string" ||
    !(typeof value.product_name === "string" || typeof value.sku_id === "string") ||
    typeof value.as_of !== "string" ||
    typeof value.source_classification !== "string" ||
    !sourceClassifications.includes(
      value.source_classification as ReservationSourceClassification,
    )
  ) {
    throw new Error(
      "Backend reservation risk item is malformed",
    );
  }

  const priority =
    value.priority === null ||
    value.priority === undefined
      ? value.priority
      : typeof value.priority === "number"
        ? value.priority
        : typeof value.priority === "string" &&
          riskLevels.includes(
            value.priority as RiskLevel,
          )
        ? (value.priority as RiskLevel)
        : (() => {
            throw new Error(
              "Reservation priority is malformed",
            );
          })();

  return {
    reservation_id: value.reservation_id,
    product_name: typeof value.product_name === "string" ? value.product_name : value.sku_id as string,

    sku_id:
      value.sku_id === null ||
      typeof value.sku_id === "string"
        ? value.sku_id
        : undefined,

    required_qty: parseNullableNumber(
      value.required_qty,
      "required_qty",
    ),

    secured_qty: parseNullableNumber(
      value.secured_qty,
      "secured_qty",
    ),

    confirmed_incoming: parseNullableNumber(
      value.confirmed_incoming_qty !== undefined ? value.confirmed_incoming_qty : value.confirmed_incoming ?? null,
      "confirmed_incoming",
    ),

    tentative_incoming: parseNullableNumber(
      value.tentative_incoming_qty !== undefined ? value.tentative_incoming_qty : value.tentative_incoming ?? null,
      "tentative_incoming",
    ),

    shortage: parseNullableNumber(
      value.shortage,
      "shortage",
    ),

    confirmed_incoming_qty: value.confirmed_incoming_qty === undefined ? undefined : parseNullableNumber(value.confirmed_incoming_qty, "confirmed_incoming_qty"),
    tentative_incoming_qty: value.tentative_incoming_qty === undefined ? undefined : parseNullableNumber(value.tentative_incoming_qty, "tentative_incoming_qty"),
    calculation_status: typeof value.calculation_status === "string" ? value.calculation_status : undefined,

    aging:
      value.aging === null ||
      value.aging === undefined
        ? value.aging
        : typeof value.aging === "number"
          ? value.aging
          : undefined,

    priority,

    as_of: value.as_of,

    source_classification:
      value.source_classification as ReservationSourceClassification,

    required_state: parseOptionalValueState(
      value.required_state,
    ),

    secured_state: parseOptionalValueState(
      value.secured_state,
    ),

    confirmed_incoming_state:
      parseOptionalValueState(
        value.confirmed_incoming_state,
      ),

    tentative_incoming_state:
      parseOptionalValueState(
        value.tentative_incoming_state,
      ),

    shortage_state: parseOptionalValueState(
      value.shortage_state,
    ),

    evidence_ids:
      Array.isArray(value.evidence_ids) &&
      value.evidence_ids.every(
        (item) => typeof item === "string",
      )
        ? value.evidence_ids
        : undefined,
  };
}

function parseEnvelope(
  value: unknown,
): ApiEnvelope<unknown[]> {
  if (
    !isRecord(value) ||
    value.schema_version !== "1.0" ||
    typeof value.tenant_id !== "string" ||
    typeof value.request_id !== "string" ||
    typeof value.trace_id !== "string" ||
    !Array.isArray(value.data) ||
    !Array.isArray(value.evidence_ids) ||
    !Array.isArray(value.warnings) ||
    typeof value.as_of !== "string"
  ) {
    throw new Error(
      "Backend reservation envelope is malformed",
    );
  }

  return value as unknown as ApiEnvelope<unknown[]>;
}
export function parseDay09ReservationsResponse(
  value: unknown,
): ApiEnvelope<ReservationRiskItem[]> {
  const envelope = parseEnvelope(value);

  return {
    ...envelope,
    data: envelope.data.map(
      parseReservationRiskItem,
    ),
  };
}

export async function getDay09Reservations(
  signal?: AbortSignal,
): Promise<ApiEnvelope<ReservationRiskItem[]>> {
  if (!useRealBackend) {
    throw new Error(
      "Day 9 actual reservation adapter requires real backend mode",
    );
  }

  const rawResponse = await realApiGet(
    "/api/v1/reservations",
    signal,
  );

  return parseDay09ReservationsResponse(
    rawResponse,
  );
}
