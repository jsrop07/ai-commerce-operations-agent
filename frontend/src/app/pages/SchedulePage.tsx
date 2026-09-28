import {
  useEffect,
  useState,
} from "react";

import {
  getDay10DelayImpacts,
  getDay10Dependencies,
  getDay10LaunchEvents,
  getDay10ReplanProposals,
  getDay10Tasks,
  parseDay10DelayImpactsResponse,
  parseDay10DependenciesResponse,
  parseDay10LaunchEventsResponse,
  parseDay10ReplanProposalsResponse,
  parseDay10TasksResponse,
} from "../../api/day10";

import ImpactPanel from "../../features/schedule/ImpactPanel";
import ReplanReview from "../../features/schedule/ReplanReview";
import ScheduleBoard from "../../features/schedule/ScheduleBoard";
import type { ScheduleTask, ReservationShortageTask } from "../../types/contracts";

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
  }, []);

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
                impacts.map((impact) => (
                  <ImpactPanel
                    key={impact.incomingId}
                    model={impact}
                  />
                ))
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
                replans.map((replan) => (
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
