import { useEffect, useRef, useState } from "react";
import { getPolicyExplanation, type Explanation } from "../../api/explanations";
import type { C04Key } from "../../api/day04";
import EvidenceDrawer from "../../components/EvidenceDrawer";
import { BackendHttpError } from "../../api/backendHttp";

const QUESTION = "예약상품은 언제 출고해?";

const warningText: Record<string, string> = {
  UNSUPPORTED_CLAIM: "현재 지원하지 않는 분석입니다.",
  CLAIM_SUPPORT_INSUFFICIENT: "현재 근거만으로 설명할 수 없습니다.",
  CLAIM_SUPPORT_UNVERIFIED: "근거의 지원 여부를 확인할 수 없습니다.",
  NO_SOURCE: "설명에 필요한 근거가 없습니다.",
  STALE_EVIDENCE: "자료가 오래되어 확인이 필요합니다.",
  MAPPING_AMBIGUOUS: "원문 근거 연결을 확인해야 합니다.",
  SOURCE_CONFLICT: "근거 자료 사이에 충돌이 있습니다.",
  TARGET_UNVERIFIED: "근거 대상을 확인할 수 없습니다.",
  FORBIDDEN_INPUT: "요청에 허용되지 않는 정보가 포함되었습니다.",
  RUNTIME_UNAVAILABLE: "설명 서비스를 현재 사용할 수 없습니다.",
  NOT_SUPPORTED_C02_RUNTIME_SOURCE_MISSING: "현재 필요한 예약 집계 자료가 없어 설명할 수 없습니다.",
  MODEL_VALIDATION_FAILED: "설명 검증을 통과하지 못했습니다.",
  MODEL_HOLD: "설명 결과를 보류했습니다.",
  C06_RUNTIME_OR_PROVIDER_FAILURE: "설명 처리 중 오류가 발생했습니다.",
  C24_QUOTA_EXCEEDED: "이 Demo Session의 AI 모델 사용 한도에 도달했습니다.",
  C24_QUOTA_UNCONFIGURED: "Public Demo의 AI 모델 호출이 현재 중지되어 있습니다.",
  C24_QUOTA_UNAVAILABLE: "Public Demo의 AI 모델 호출이 현재 중지되어 있습니다.",
  C24_SESSION_REQUIRED: "Demo Session이 필요합니다. 새 세션을 시작해 주세요.",
};

export function explanationWarning(reason: string): string {
  const code = reason.split(":", 1)[0];
  return warningText[code] ?? `확인 필요 (${code})`;
}

export default function PolicyExplanation({ targetId, productName }: { targetId: string; productName: string }) {
  const [phase, setPhase] = useState<"idle" | "loading" | "answer" | "hold" | "error">("idle");
  const [errorText, setErrorText] = useState("설명을 불러오지 못했습니다.");
  const [result, setResult] = useState<Explanation | null>(null);
  const [c04Key, setC04Key] = useState<C04Key | undefined>();
  const controllerRef = useRef<AbortController | null>(null);
  const sequenceRef = useRef(0);
  const activeRef = useRef(true);

  useEffect(() => {
    activeRef.current = true;
    return () => {
      activeRef.current = false;
      sequenceRef.current += 1;
      controllerRef.current?.abort();
    };
  }, []);

  function request() {
    if (controllerRef.current) return;
    const controller = new AbortController();
    const sequence = ++sequenceRef.current;
    controllerRef.current = controller;
    setPhase("loading");
    setResult(null);
    getPolicyExplanation(QUESTION, controller.signal)
      .then((response) => {
        if (!activeRef.current || controller.signal.aborted || sequence !== sequenceRef.current) return;
        setResult(response.data); // request_id remains in the internal result only.
        setPhase(response.data.status === "ANSWER" ? "answer" : "hold");
      })
      .catch((error: unknown) => {
        if (activeRef.current && !controller.signal.aborted && sequence === sequenceRef.current) {
          setErrorText(error instanceof BackendHttpError && error.status === 429 ?
            "요청이 잠시 제한되었습니다. 잠시 후 다시 시도해 주세요." :
            error instanceof BackendHttpError && error.status >= 500 ?
              "AI 설명 제공자가 일시적으로 응답하지 않습니다." : "설명을 불러오지 못했습니다.");
          setPhase("error");
        }
      })
      .finally(() => {
        if (controllerRef.current === controller) controllerRef.current = null;
      });
  }

  return <section className="card card-body stack" data-testid="policy-explanation" data-target-id={targetId}>
    <strong>{productName} · 예약상품 출고 정책</strong>
    <p className="muted">공통 출고 정책을 확인합니다. 이 예약의 수량이나 출고 가능 여부를 판정하지 않습니다.</p>
    <button type="button" onClick={request} disabled={phase === "loading"}>
      {phase === "loading" ? "설명 생성 중" : phase === "idle" ? "정책 설명 보기" : "정책 설명 다시 확인"}
    </button>
    {phase === "loading" && <p role="status">설명 생성 중입니다.</p>}
    {phase === "error" && <p role="alert">{errorText}</p>}
    {phase === "hold" && result && <div className="notice" role="status">
      <strong>확인 필요</strong>
      <p>{result.warnings.some((reason) => reason.startsWith("C24_")) ?
        "AI 모델 호출 상태를 확인해 주세요. 기존 검증 근거는 별도로 확인할 수 있습니다." :
        "현재 근거만으로 설명할 수 없습니다."}</p>
      <ul>{result.warnings.map((reason) => <li key={reason}>{explanationWarning(reason)}</li>)}</ul>
      <p>자료 모드: 예시 데이터 (SYNTHETIC_DEMO)</p>
    </div>}
    {phase === "answer" && result && <div className="stack" role="status">
      <strong>정책 설명 · 예시 데이터 (SYNTHETIC_DEMO)</strong>
      <p>{result.conclusion}</p>
      <div><strong>사용 근거</strong><ul>{result.used_facts.map((fact, index) => <li key={index}>{fact}</li>)}</ul></div>
      <div><strong>사용 수치 사실</strong>{result.used_numeric_facts.length === 0 ? <p>없음</p> :
        <ul>{result.used_numeric_facts.map((fact, index) => <li key={index}>{fact.field}: {fact.value} {fact.unit}</li>)}</ul>}</div>
      <div><strong>인용 근거</strong><ul>{result.citations.map((citation, index) => {
        const lookup = result.c04_lookup.find((key) => key.source_id === citation.source_id && key.version === citation.version);
        return <li key={`${citation.source_id}-${citation.version}-${index}`}>
          {citation.source_id} · {citation.version}{" "}
          <button type="button" disabled={!lookup} onClick={() => setC04Key(lookup)}>원문 근거 열기</button>
          {!lookup && <span> 원문 연결 없음</span>}
        </li>;
      })}</ul></div>
      {result.next_check && <p>다음 확인: {result.next_check}</p>}
    </div>}
    <EvidenceDrawer open={!!c04Key} insight={null} c04Key={c04Key} onClose={() => setC04Key(undefined)} />
  </section>;
}
