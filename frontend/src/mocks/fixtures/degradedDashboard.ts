export interface ProviderFailureFixture {
  provider: "CAFE24" | "TOSS_POS" | "ECOUNT";
  reason: "TIMEOUT";
  last_success_as_of: string;
}

export const providerFailureFixture: ProviderFailureFixture = {
  provider: "ECOUNT",
  reason: "TIMEOUT",
  last_success_as_of: "2026-09-03T10:30:00Z",
};