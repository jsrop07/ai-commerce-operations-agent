import { useState } from "react";
import { ConfidenceBadge } from "../../components/StatusBadges";

type MappingCandidate = {
  sku_id: string;
  label: string;
  confidence: number;
  rule: string;
};

type MappingReviewItem = {
  id: string;
  source: string;
  originalName: string;
  candidates: readonly MappingCandidate[];
};

type MappingReviewProps = {
  items: readonly MappingReviewItem[];
  environment: "DEMO" | "PRODUCTION_READ";
};

export default function MappingReview({
  items,
  environment,
}: MappingReviewProps) {
  const [selectedByItem, setSelectedByItem] =
    useState<Record<string, string | null>>({});

  const [savedByItem, setSavedByItem] =
    useState<Record<string, string | null>>({});

  const isDemo = environment === "DEMO";

  return (
    <section
      className="mapping-review"
      aria-labelledby="mapping-review-title"
    >
      <div className="card-header">
        <div>
          <h2 id="mapping-review-title">
            상품 연결 검토
          </h2>
          <p className="muted">
            후보가 있어도 자동으로 연결하지 않습니다.
            운영자가 후보와 근거를 직접 확인해야 합니다.
          </p>
          <p className="muted">
            현재 목록은 Frontend Demo View Model이며 실제 Backend
            Mapping Projection이 아닙니다.
          </p>
        </div>
      </div>

      <div className="stack">
        {items.map((item) => {
          const selectedSku =
            selectedByItem[item.id] ?? null;

          const savedSku =
            savedByItem[item.id] ?? null;
          const itemTitleId = `mapping-review-item-${item.id}`;
          const saveDescriptionId =
            `mapping-review-save-description-${item.id}`;

          return (
            <article
              className="card mapping-review-item"
              key={item.id}
              aria-labelledby={itemTitleId}
            >
              <div className="card-body stack">
                <div className="mapping-review-source">
                  <span className="badge">
                    {item.source}
                  </span>

                  <strong id={itemTitleId}>
                    {item.originalName}
                  </strong>
                </div>

                {item.candidates.length === 0 ? (
                  <div className="notice warning">
                    연결 가능한 SKU 후보가 없습니다.
                    자동 연결하지 않고 미연결 상태로 유지합니다.
                  </div>
                ) : (
                  <div
                    className="mapping-candidate-list"
                    role="group"
                    aria-label={`${item.originalName} SKU 후보`}
                  >
                    {item.candidates.map((candidate) => {
                      const selected =
                        selectedSku === candidate.sku_id;

                      return (
                        <button
                          key={candidate.sku_id}
                          type="button"
                          className={`mapping-candidate ${
                            selected ? "selected" : ""
                          }`}
                          aria-pressed={selected}
                          onClick={() => {
                            setSelectedByItem((current) => ({
                              ...current,
                              [item.id]:
                                current[item.id] ===
                                candidate.sku_id
                                  ? null
                                  : candidate.sku_id,
                            }));
                          }}
                        >
                          <span>
                            <strong>
                              {candidate.label}
                            </strong>

                            <span className="muted">
                              {candidate.rule}
                            </span>
                          </span>

                          <ConfidenceBadge
                            confidence={
                              candidate.confidence
                            }
                          />
                        </button>
                      );
                    })}
                  </div>
                )}

                <div className="mapping-review-actions">
                  {selectedSku && (
                    <button
                      type="button"
                      className="filter"
                      onClick={() => {
                        setSelectedByItem((current) => ({
                          ...current,
                          [item.id]: null,
                        }));
                      }}
                    >
                      선택 취소
                    </button>
                  )}

                  <button
                    type="button"
                    className="filter active"
                    aria-describedby={saveDescriptionId}
                    disabled={
                      !isDemo ||
                      !selectedSku ||
                      item.candidates.length === 0
                    }
                    onClick={() => {
                      if (!isDemo || !selectedSku) {
                        return;
                      }

                      setSavedByItem((current) => ({
                        ...current,
                        [item.id]: selectedSku,
                      }));
                    }}
                  >
                    Demo 검토 결정 저장
                  </button>
                </div>

                <p
                  id={saveDescriptionId}
                  className="muted mapping-review-save-description"
                >
                  {isDemo
                    ? selectedSku
                      ? "검토 결정은 현재 브라우저의 Demo 로컬 상태에만 저장되며 외부 Provider에는 적용되지 않습니다."
                      : "후보를 선택해야 저장할 수 있습니다. 검토 결정은 Demo 로컬 상태에만 저장됩니다."
                    : "Production Read-Only에서는 저장할 수 없으며 외부 Provider에도 적용되지 않습니다."}
                </p>

                {savedSku && isDemo && (
                  <p
                    className="notice"
                    role="status"
                  >
                    Demo 검토 결정이 저장되었습니다:
                    {" "}
                    <strong>{savedSku}</strong>
                  </p>
                )}

              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
