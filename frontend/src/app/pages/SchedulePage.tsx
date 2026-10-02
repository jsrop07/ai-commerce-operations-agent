import {
  useEffect,
  useRef,
  useState,
} from "react";

import {
  getDay10DelayImpacts,
  getDay10DelayImpact,
  getDay10Dependencies,
  getDay10LaunchEvents,
  getDay10ReplanProposals,
  getDay10Tasks,
  prepareDay10DemoSchedule,
  draftDay10DemoReplan,
  parseDay10DelayImpactsResponse,
  parseDay10DependenciesResponse,
  parseDay10LaunchEventsResponse,
  parseDay10ReplanProposalsResponse,
  parseDay10TasksResponse,
} from "../../api/day10";

import ImpactPanel from "../../features/schedule/ImpactPanel";
import ReplanReview from "../../features/schedule/ReplanReview";
import ScheduleBoard from "../../features/schedule/ScheduleBoard";
import type { ScheduleTask, ReservationShortageTask, ScheduleDelayImpact } from "../../types/contracts";

const scheduleTasks = (tasks: (ScheduleTask | ReservationShortageTask)[]): ScheduleTask[] =>
  tasks.filter((task): task is ScheduleTask => "flow" in task);

import {
  buildDelayImpactViewModel,
  type DelayImpactViewModel,
} from "../../features/schedule/impactViewModel";

import {
  buildReplanReviewViewModel,
  type ReplanReviewViewModel,
} from "../../features/schedule/replanViewModel";

import {
  buildScheduleBoardViewModel,
  type ScheduleBoardViewModel,
} from "../../features/schedule/viewModel";

import {
  mockApiGet,
} from "../../mocks/handlers";

const useRealBackend =
  import.meta.env.VITE_USE_REAL_BACKEND === "true";
const demoEnabled = useRealBackend && import.meta.env.VITE_SCHEDULE_DEMO === "true";

type LoadState =
  | "LOADING"
  | "READY"
  | "ERROR";

export default function SchedulePage() {
  const [
    loadState,
    setLoadState,
  ] = useState<LoadState>("LOADING");

  const [
    model,
    setModel,
  ] = useState<ScheduleBoardViewModel | null>(
    null,
  );

  const [
    impacts,
    setImpacts,
  ] = useState<DelayImpactViewModel[]>([]);
  const [rawImpacts, setRawImpacts] = useState<ScheduleDelayImpact[]>([]);
  const [selectedIncomingId, setSelectedIncomingId] = useState<string | null>(null);
  const selectedIncomingRef = useRef<string | null>(null);
  const [selectedImpact, setSelectedImpact] = useState<DelayImpactViewModel | null>(null);
  const [detailState, setDetailState] = useState<LoadState>("READY");
  const [detailError, setDetailError] = useState<string | null>(null);
  const [actionState, setActionState] = useState<"IDLE" | "PREPARING" | "DRAFTING">("IDLE");
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const actionBusy = useRef(false);
  selectedIncomingRef.current = selectedIncomingId;

  const [
    replans,
    setReplans,
  ] = useState<ReplanReviewViewModel[]>([]);

  const [
    errorMessage,
    setErrorMessage,
  ] = useState<string | null>(null);

  useEffect(() => {
    const controller =
      new AbortController();

    async function loadSchedule() {
      setLoadState("LOADING");
      setErrorMessage(null);
      setModel(null);
      setSelectedImpact(null);

      try {
        if (useRealBackend) {
          /*
           * Actual mode
           *
           * 실제 Backend만 사용한다.
           * Actual 요청 실패 시 Fixture로 fallback하지 않는다.
           */
          const [
            launchResponse,
            taskResponse,
            dependencyResponse,
            impactResponse,
            replanResponse,
          ] = await Promise.all([
            getDay10LaunchEvents(
              controller.signal,
            ),

            getDay10Tasks(
              controller.signal,
            ),

            getDay10Dependencies(
              controller.signal,
            ),

            getDay10DelayImpacts(
              controller.signal,
            ),

            getDay10ReplanProposals(
              controller.signal,
            ),
          ]);

          if (controller.signal.aborted) {
            return;
          }

          setModel(
            buildScheduleBoardViewModel(
              launchResponse.data,
              scheduleTasks(taskResponse.data),
              dependencyResponse.data,
            ),
          );

          setImpacts(
            impactResponse.data.map(
              buildDelayImpactViewModel,
            ),
          );
          setRawImpacts(impactResponse.data);
          setSelectedIncomingId((current) => impactResponse.data.some((item) => item.incoming_id === current)
            ? current : impactResponse.data[0]?.incoming_id ?? null);

          setReplans(
            replanResponse.data.map(
              buildReplanReviewViewModel,
            ),
          );

          setLoadState("READY");
          return;
        }

        /*
         * Mock / Fixture mode
         *
         * Fixture도 Actual과 동일한 parser를 거친다.
         * Frontend 계약 검증을 우회하지 않는다.
         */
        const [
          launchRaw,
          taskRaw,
          dependencyRaw,
          impactRaw,
          replanRaw,
        ] = await Promise.all([
          mockApiGet<unknown>(
            "/api/v1/launch-events",
          ),

          mockApiGet<unknown>(
            "/api/v1/tasks",
          ),

          mockApiGet<unknown>(
            "/api/v1/schedule/dependencies",
          ),

          mockApiGet<unknown>(
            "/api/v1/schedule/delay-impacts",
          ),

          mockApiGet<unknown>(
            "/api/v1/schedule/replan-proposals",
          ),
        ]);

        if (controller.signal.aborted) {
          return;
        }

        const launchResponse =
          parseDay10LaunchEventsResponse(
            launchRaw,
          );

        const taskResponse =
          parseDay10TasksResponse(
            taskRaw,
          );

        const dependencyResponse =
          parseDay10DependenciesResponse(
            dependencyRaw,
          );

        const impactResponse =
          parseDay10DelayImpactsResponse(
            impactRaw,
          );

        const replanResponse =
          parseDay10ReplanProposalsResponse(
            replanRaw,
          );

        setModel(
          buildScheduleBoardViewModel(
            launchResponse.data,
            scheduleTasks(taskResponse.data),
            dependencyResponse.data,
          ),
        );

        setImpacts(
          impactResponse.data.map(
            buildDelayImpactViewModel,
          ),
        );
        setRawImpacts(impactResponse.data);
        setSelectedIncomingId((current) => impactResponse.data.some((item) => item.incoming_id === current)
          ? current : impactResponse.data[0]?.incoming_id ?? null);

        setReplans(
          replanResponse.data.map(
            buildReplanReviewViewModel,
          ),
        );

        setLoadState("READY");
      } catch (error) {
        if (controller.signal.aborted) {
          return;
        }

        /*
         * Fail Closed
         *
         * 오류 시 기존 데이터나 Fixture를
         * 대신 보여주지 않는다.
         */
        setModel(null);
        setImpacts([]);
        setRawImpacts([]);
        setReplans([]);

        setLoadState("ERROR");

        setErrorMessage(
          error instanceof Error
            ? error.message
            : "일정 데이터를 불러오지 못했습니다.",
        );
      }
    }

    void loadSchedule();

    return () => {
      controller.abort();
    };
  }, [reloadKey]);

  useEffect(() => {
    if (loadState !== "READY" || selectedIncomingId === null) return;
    const controller = new AbortController();
    const listed = impacts.find((item) => item.incomingId === selectedIncomingId) ?? null;
    setSelectedImpact(null);
    setDetailState("LOADING");
    setDetailError(null);
    if (!useRealBackend) {
      setSelectedImpact(listed);
      setDetailState("READY");
      return () => controller.abort();
    }
    void getDay10DelayImpact(selectedIncomingId, controller.signal).then((item) => {
      if (!controller.signal.aborted) {
        setSelectedImpact(buildDelayImpactViewModel(item));
        setDetailState("READY");
      }
    }).catch((error) => {
      if (!controller.signal.aborted) {
        setDetailError(error instanceof Error ? error.message : "영향 상세를 불러오지 못했습니다.");
        setDetailState("ERROR");
      }
    });
    return () => controller.abort();
  }, [loadState, selectedIncomingId, impacts]);

  async function prepareDemo() {
    if (!demoEnabled || actionBusy.current) return;
    actionBusy.current = true;
    setActionState("PREPARING");
    setActionMessage(null);
    try {
      const result = await prepareDay10DemoSchedule();
      setActionMessage(result.status === "ALREADY_READY" ? "합성 예시가 이미 준비되어 있습니다." : "합성 예시를 준비했습니다.");
      setSelectedIncomingId("incoming-demo-001");
      setReloadKey((key) => key + 1);
    } catch (error) {
      setActionMessage(error instanceof Error ? error.message : "Demo 준비에 실패했습니다.");
    } finally {
      actionBusy.current = false;
      setActionState("IDLE");
    }
  }

  async function draftDemo() {
    if (!demoEnabled || actionBusy.current || selectedIncomingId === null) return;
    const impact = rawImpacts.find((item) => item.incoming_id === selectedIncomingId);
    if (!impact) return;
    actionBusy.current = true;
    setActionState("DRAFTING");
    setActionMessage(null);
    try {
      const proposal = await draftDay10DemoReplan(impact);
      if (selectedIncomingRef.current === impact.incoming_id) {
        const view = buildReplanReviewViewModel(proposal);
        setReplans((current) => [view, ...current.filter((item) => item.proposalId !== view.proposalId)]);
        setActionMessage("재계획 제안을 생성했습니다. 현재 일정은 변경되지 않았습니다.");
      }
    } catch (error) {
      setActionMessage(error instanceof Error ? error.message : "Demo 제안 생성에 실패했습니다.");
    } finally {
      actionBusy.current = false;
      setActionState("IDLE");
    }
  }

  return (
    <main className="page">
      <header className="page-header">
        <div>
          <h2>운영 일정</h2>

          <p className="muted">
            출시·입고 일정, 지연 영향,
            재계획 제안을 검토합니다.
          </p>
        </div>

        <div>
          <span className="badge">
            {useRealBackend
              ? "Actual Backend"
              : "Fixture / Demo"}
          </span>
        </div>
      </header>
      {demoEnabled && <section className="card"><div className="card-body stack">
        <p>격리 합성 예시 검증 (SYNTHETIC_DEMO) · 실제 사업 입고 자료 아님</p>
        <button type="button" disabled={actionState !== "IDLE"} onClick={() => void prepareDemo()}>
          {actionState === "PREPARING" ? "준비 중..." : "C08 Demo 명시적으로 준비"}
        </button>
        {actionMessage && <p role="status">{actionMessage}</p>}
      </div></section>}

      {loadState === "LOADING" && (
        <section
          className="card"
          aria-live="polite"
          aria-busy="true"
        >
          <div className="card-body">
            <p>
              일정 데이터를 불러오는 중입니다.
            </p>
          </div>
        </section>
      )}

      {loadState === "ERROR" && (
        <section
          className="card"
          role="alert"
        >
          <div className="card-body">
            <h3>
              일정 데이터를 사용할 수 없습니다.
            </h3>

            <p>
              Backend 응답을 확인할 수 없어
              일정 정보를 표시하지 않습니다.
            </p>

            {errorMessage !== null && (
              <p className="tertiary">
                오류: {errorMessage}
              </p>
            )}

            <p className="muted">
              오류 상태에서는 Fixture나 임의 일정으로
              대체하지 않습니다.
            </p>
          </div>
        </section>
      )}

      {loadState === "READY" &&
        model !== null && (
          <>
            <ScheduleBoard
              model={model}
            />

            <section
              aria-labelledby="delay-impact-list-title"
            >
              <h2 id="delay-impact-list-title">
                입고 지연 영향
              </h2>

              {impacts.length === 0 ? (
                <div className="card">
                  <div className="card-body">
                    <p>
                      현재 표시할 지연 영향 데이터가
                      없습니다.
                    </p>
                  </div>
                </div>
              ) : (
                <>
                  <label htmlFor="schedule-incoming">Incoming 선택</label>
                  <select id="schedule-incoming" value={selectedIncomingId ?? ""}
                    onChange={(event) => { selectedIncomingRef.current = event.target.value; setSelectedIncomingId(event.target.value); }}>
                    {impacts.map((impact) => <option key={impact.incomingId} value={impact.incomingId}>{impact.incomingId}</option>)}
                  </select>
                  {detailState === "LOADING" && <p>영향 상세를 불러오는 중입니다.</p>}
                  {detailState === "ERROR" && <p role="alert">영향 상세를 확인할 수 없습니다. {detailError}</p>}
                  {detailState === "READY" && selectedImpact && <ImpactPanel key={selectedImpact.incomingId} model={selectedImpact} />}
                  {demoEnabled && selectedImpact?.dataMode === "SYNTHETIC_DEMO" &&
                    <button type="button" disabled={actionState !== "IDLE"} onClick={() => void draftDemo()}>
                      {actionState === "DRAFTING" ? "제안 생성 중..." : "합성 예시 재계획 제안 생성"}
                    </button>}
                </>
              )}
            </section>

            <section
              aria-labelledby="replan-review-list-title"
            >
              <h2 id="replan-review-list-title">
                재계획 검토
              </h2>

              {replans.length === 0 ? (
                <div className="card">
                  <div className="card-body">
                    <p>
                      현재 검토할 재계획 제안이
                      없습니다.
                    </p>
                  </div>
                </div>
              ) : (
                replans.filter((replan) => selectedIncomingId === null || replan.sourceIncomingId === undefined || replan.sourceIncomingId === selectedIncomingId).map((replan) => (
                  <ReplanReview
                    key={replan.proposalId}
                    model={replan}
                  />
                ))
              )}
            </section>
          </>
        )}
    </main>
  );
}
