import type {
  ApiEnvelope,
  InsightSummary,
} from "../types/contracts";
import { urgentQueueFixtures } from "./fixtures/urgentQueue";

const evidenceByRequestId = new Map<
  string,
  ApiEnvelope<InsightSummary>
>(
  urgentQueueFixtures.map((item) => [
    item.request_id,
    item,
  ]),
);

export async function mockGetEvidenceByRequestId(
  requestId: string,
): Promise<ApiEnvelope<InsightSummary> | null> {
  return evidenceByRequestId.get(requestId) ?? null;
}