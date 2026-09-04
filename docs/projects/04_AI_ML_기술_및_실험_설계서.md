# 04. AI·ML 기술 및 실험 설계서

> **이 문서는 무엇인가:** AI 기술 이름을 나열하는 문서가 아니라, 실제 문제마다 `문제 → 가설 → 적용 기법 → 비교 기준 → 실험 → 지표 → 결과 → 채택/기각`을 기록하는 실험 설계서다.  
> **언제 읽는가:** 프롬프트, 검색증강생성(RAG), 소형 언어모델, 그래프, 메모리, 에이전트, 모델 선택기를 구현하기 전 읽는다.  
> **완료의 뜻:** 기능이 실행되는 것만으로 끝나지 않는다. 같은 시험세트에서 기준 방법보다 나아졌고 비용·지연·오류 분석까지 기록되어야 채택한다.

## 0. AI 트랙 실행 도구와 코드 생성 경계

AI 트랙은 AI·ML Chat 질문지가 실험 책임자를 맡고, 로컬 터미널·모델 API·RunPod GPU에서 실행한다. AI 질문지가 Codex 사용을 전제로 안내하지 않는다.

- 문서·Dataset manifest·Golden Set·Prompt·Config는 AI 질문지가 완성된 내용을 제공하고 사용자가 지정 경로에 저장한다.
- QLoRA처럼 GPU가 필요한 작업은 RunPod에서 실행한다. Codex는 학습 실행 환경이 아니다.
- 프로젝트 공통 모듈, API 연결, 여러 파일에 걸친 구현이 필요하면 `Codex 대기 항목`으로 기록하여 다음 통합 구현 묶음에 전달한다.
- 파일 존재 여부를 먼저 확인하지 않고 `python -m ...` 또는 `pytest ...`를 실행시키지 않는다.
- 실행 파일이나 Fixture가 없으면 먼저 생성 절차를 완료하며, `ModuleNotFoundError`는 실험 실패가 아니라 사전 구현 누락으로 판정한다.
- AI 트랙은 결과를 `문제 → 가설 → 적용 기법 → Baseline → 실험 → Metric → 결과 → 채택/기각` 구조로 판정하고, Codex는 이 판단을 대신하지 않는다.

## 1. 목적과 원칙

이 문서는 AI 기술 목록이 아니라 **의사결정 가능한 실험 설계**다. 모든 기능은 다음 형식을 따른다.

> 문제 → 가설 → 적용 기법 → Baseline → 실험 → Metric → 결과 → 채택/기각

현재는 구현 전이므로 결과를 만들지 않는다. 각 Experiment의 `Result`는 실제 실행 전 `PENDING`이며, Dataset/Code/Config/Seed/Artifact/Metric/Error Sample을 함께 저장해야 `MEASURED`가 된다.

### 공통 원칙

- Rule/SQL로 정확히 풀리는 문제에는 LLM을 호출하지 않는다.
- 동일 Test Split/Golden Set으로 비교한다.
- Accuracy만 아니라 JSON validity, grounding, latency, cost, safety를 함께 본다.
- 실제 비식별 데이터는 Domain Seed와 비공개 Test에 우선 사용하고 Synthetic Train 보강이 Test로 유출되지 않게 한다.
- 기법이 이점을 보이지 않으면 사용하지 않은 이유와 결과를 Decision Log에 남긴다.

## 2. 업무 분해와 기본 처리 경로

| Task | 1차 방식 | 승격 조건 | Large LLM 사용 이유 |
|---|---|---|---|
| 재고 산술/예약 부족수량 | Rule/SQL | 없음 | 사용하지 않음: 결정론적 계산이 정확·저렴 |
| SKU exact/alias mapping | SQL/Rule | ambiguous 후보 | 복합 상품명 해석이 필요할 때만 |
| 문의 Intent/Entity | sLLM 또는 structured small model | low confidence/schema retry fail | 긴 문맥·희귀 의도 판단 |
| 상품/정책 Q&A | filter + Hybrid RAG + small model | conflicting evidence/high risk | 다중 근거 종합 |
| 운영 Task 구조화 | structured prompt/sLLM | 복합 dependency | 제약·날짜·관계 추론 |
| 일정 재계획 설명 | graph/rule optimizer + LLM explanation | 복합 충돌 | 계획 생성이 아니라 설명/대안 요약 |
| 이상징후 탐지 | Rule/statistical model | 원인 설명 필요 | 탐지는 비LLM, 설명만 LLM |
| 환불/취소/가격/PII | policy deny + human | 없음 | 자동 실행에 사용하지 않음 |

## 3. 데이터셋 관리 원칙

### 3.1 데이터 분류체계

| Dataset | Unit | Label/Target | 출처 | 용도 |
|---|---|---|---|---|
| Inquiry NLU | inquiry turn/thread | intent, entities, risk, lookup flags | 비식별 실제 + 공개 + synthetic | sLLM/prompt eval |
| Operations NLU | operator instruction | event/task JSON, date/dependency | human-written + synthetic validation | structured extraction |
| Retrieval Corpus | product/policy/order/inquiry relation record | metadata, valid time, source | 비식별 operational + demo | RAG index |
| Retrieval Golden | query | relevant IDs/graded relevance | 실제 질문 seed + human judgment | Recall/MRR/nDCG |
| Graph Query Set | multi-hop query | answer/path/relevant nodes | domain expert curated | graph comparison |
| Agent Scenario | event/state/failure injection | expected transition/tool/policy | synthetic + sanitized incident pattern | workflow eval |
| Inventory Backtest | SKU-date | observed demand/risk outcome | 비식별 sales/stock | rule/stat baseline |

### 3.2 실제/공개/합성 데이터 비율

고정 비율을 먼저 선언하지 않는다. 실제 데이터 규모와 class coverage를 측정한 후 다음 정책을 적용한다.

- 실제 데이터: Domain 표현과 비공개 Validation/Test의 중심. 고객 단위 split 또는 시간 split으로 leakage 방지.
- 공개 데이터: 일반 언어 다양성 보강. 보드게임/상거래 License와 재배포 조건 기록.
- Synthetic: 희귀 Intent, 경계 사례, JSON 오류 복구, failure scenario 보강. 생성 모델/Prompt version과 human validation 상태 기록.
- Test Set: Synthetic augmentation의 source example/near duplicate를 MinHash/embedding 유사도 검사로 제거.

권장 시작 가설은 Train에서 실제 40~60%, 공개 10~20%, 검수 Synthetic 20~40% 범위이며 **목표가 아니라 실험 입력**이다. Validation/Test는 실제 비식별 비중을 최대로 한다.

### 3.3 개인정보와 학습·검증·시험 분리

1. PII detector + rule redaction
2. human spot check
3. placeholder token (`<CUSTOMER>`, `<PHONE>`)으로 entity boundary 보존
4. raw vault와 de-identified artifact 분리
5. customer/thread/time 기준 group split
6. train/validation/test manifest hash 고정
7. 공개 Artifact에는 synthetic/demo test만 제공; 실제 Test metric은 집계치만 공개

### 3.4 불균형 분석

- 먼저 Intent/Issue Type/Entity coverage와 confusion을 분석한다. Brand별 균등화를 목표로 하지 않는다.
- loss weighting, minority oversampling, targeted synthetic augmentation을 순서대로 비교한다.
- undersampling은 빈번한 정상 표현의 다양성을 잃을 수 있으므로 latency/학습비용 문제가 있을 때만 쓴다.
- Macro F1과 per-class support/confusion을 함께 기록한다.

## 4. 프롬프트 엔지니어링

### 4.1 업무별 기법 선택

| Task | 후보 | 선택 가설 | 사용하지 않는 방식/이유 |
|---|---|---|---|
| Intent/Entity baseline | zero-shot schema, few-shot schema | 희귀/경계 표현은 few-shot이 F1/validity 개선 | ReAct 불필요: tool planning 없음 |
| 운영 Task 추출 | structured instruction + schema + few-shot | date/dependency 예시가 field accuracy 개선 | 자유 Role-play는 일관성 저하 가능 |
| RAG 답변 Draft | instruction/data 분리 + citation schema + self-check | grounded answer와 abstention 개선 | 공개 CoT 의존 금지; 검증 가능한 필드로 reasoning 결과만 요구 |
| Agent decision | ReAct-like tool/action observation | 여러 도구와 분기가 있을 때만 유효 | 단일 lookup은 direct call |
| 일정 설명 | constrained structured output | 기존/제안 diff와 이유를 안정적으로 반환 | 모델 단독 계획 생성 금지 |

### 4.2 프롬프트 구성

- System policy: 역할, 금지행동, risk route, data boundary
- Task instruction: 목표와 성공 조건
- Context envelope: trusted/untrusted source 구분, `as_of`, tenant
- Examples: 대표·경계·abstain 예시, Test와 중복 금지
- Output schema: JSON Schema/Pydantic, enum, nullable reason
- Verification fields: `evidence_ids`, `confidence`, `missing_fields`, `risk_level`
- Self-check: 답을 다시 길게 추론시키지 않고 `schema/evidence/policy` 체크리스트 결과만 반환

### 4.3 프롬프트 비교실험 PROMPT-01/02

| 항목 | PROMPT-01 NLU | PROMPT-02 Grounded Draft |
|---|---|---|
| 문제 | 문의 구조화 오류 | 근거 없는 답변/인용 누락 |
| 가설 | few-shot+schema가 zero-shot보다 Macro F1/validity 개선 | citation schema+self-check가 groundedness 개선 |
| Baseline | zero-shot plain JSON | RAG context + direct answer |
| Variants | structured zero-shot; 3/6-shot; role split; self-check | schema only; schema+self-check; compressed context |
| Metrics | Intent/Entity F1, JSON Valid, field accuracy, token, latency | faithfulness, citation precision/coverage, abstention, token, latency |
| 채택 | 품질 조건 충족 후 동일 품질이면 토큰·지연이 낮은 방식 | 인용 근거 포함률 95% 이상 목표, 근거 없는 주장 0에 가까운 방식 |
| Result | PENDING | PENDING |

Prompt는 `prompt_id`, semantic version, model compatibility, input/output schema hash, change reason, eval run을 Registry에 기록한다. Production 승격은 Golden Set regression 통과가 필요하다.

## 5. 검색과 검색증강생성(RAG)

### 5.1 문제와 가설

보드게임 상품 문의는 정확한 상품명·언어·본판/확장·구성품·재고 시점이 중요하다. BM25/metadata는 exact match에 강하고 Dense Retrieval은 자연어 표현 차이에 강하다. 따라서 Hybrid가 후보지만, Golden Set에서 이점을 입증한 후 채택한다.

### 5.2 레코드·문서 유형별 분할

| Source | 기본 단위 | 후보 Chunking | 이유 |
|---|---|---|---|
| Product/Variant | record + field sections | structure-aware | 상품명/옵션/언어/속성 경계 보존 |
| Policy/FAQ | heading/paragraph | semantic vs 300/600 token fixed, overlap 10~15% | 조항 단위와 문맥 길이 비교 |
| Inquiry history | sanitized turn pair 또는 issue episode | conversation episode | 질문-답변 관계 유지, PII 제거 |
| Order/Inventory | retrieval용 chunk 아님 | SQL/filter 결과를 evidence object로 | 최신 정확값을 embedding에서 답하지 않음 |
| Compatibility/Components | edge/record | graph/structured relation | multi-hop 관계 보존 |

Fixed-size는 baseline으로만 사용한다. 구조화 Record를 임의 token overlap으로 중복시키지 않는다.

### 5.3 검색용 부가정보

`tenant_id`, `source_type`, `source_id`, `product_id`, `sku_id`, `brand_id`, `category`, `language`, `base_game_id`, `expansion_type`, `component`, `channel`, `policy_type`, `valid_from`, `valid_to`, `updated_at`, `availability`, `pii_status`, `schema_version`, `access_scope`.

필터는 사용자 query에서 무조건 추론하지 않는다. canonical entity resolver의 confidence가 낮으면 후보를 넓히고 UI에 ambiguity를 보여준다.

### 5.4 검색어 처리 후보

1. normalize/tokenize, typo/product alias expansion
2. intent/entity와 required freshness 결정
3. metadata/tenant/access/time filter
4. query rewrite: 대명사·축약·상품 별칭 해소
5. multi-query는 관계·비교·두 개 이상 entity가 있는 질문이면서 단일-query Retrieval의 top-10 relevant hit가 없는 경우에만 최대 3개 사용한다. 상품명/SKU exact query와 live inventory 단일 조회에는 사용하지 않는다.
6. BM25와 Dense 병렬 검색
7. RRF/weighted fusion
8. duplicate/near-duplicate collapse
9. cross-encoder rerank
10. context compression: query-relevant field/문장만, numeric live data는 SQL evidence 유지
11. confidence/freshness/citation validation
12. failure fallback: SQL/exact lookup→clarification/abstain→human

### 5.5 검색 비교실험 표

| Exp | 비교 | 통제 | Metric | 채택 기준 | Result |
|---|---|---|---|---|---|
| RAG-01 | fixed 300/600/900 vs structure-aware | same embedding/index/query | Recall@5/10, nDCG@10, chunk redundancy | structure-aware가 유의 개선 또는 token 절감 | PENDING |
| RAG-02 | overlap 0/10/20% | policy corpus | Recall, duplicate rate, context token | 품질-중복 Pareto | PENDING |
| RAG-03 | BM25 vs vector vs hybrid | same Golden Set/top-k | Recall@K, Precision@K, MRR, nDCG | query slice별 우세 분석 | PENDING |
| RAG-04 | hybrid vs +reranker | candidate K fixed | nDCG/MRR, p95 latency, cost | quality gain이 latency budget 내 | PENDING |
| RAG-05 | 상위 문서 수 3/5/10/20 | 선택된 검색 흐름 | 답변 근거성, 토큰, 지연 | 최소 문맥으로 품질 조건 충족 | 대기 |
| RAG-06 | rewrite/multi-query on/off | ambiguity slices | recall, false expansion, token | 복합 query에만 이점 시 conditional | PENDING |
| RAG-07 | full context vs compression | answer model fixed | faithfulness, coverage, token | 품질 유지하며 token ≥20% 절감 목표 | PENDING |

Golden relevance는 binary뿐 아니라 0~3 graded judgment를 포함해 nDCG를 계산한다. Product exact, typo, Korean/English alias, expansion compatibility, component, inventory freshness, policy, no-answer slice를 분리 보고한다.

### 5.6 신뢰도, 캐시, 최신성

- confidence feature: top score, margin, lexical+dense agreement, entity confidence, source count, freshness, reranker score
- calibration set으로 `answer/retrieve_more/clarify/abstain` threshold를 정한다.
- cache key: normalized query + tenant + access + metadata filter + index version + data freshness bucket
- 상품 설명/정책은 version invalidation, 재고/주문은 짧은 TTL 또는 cache 금지
- citation은 source ID, field/section, updated_at/as_of를 반환한다.

## 6. 여러 차례 대화와 메모리

### 6.1 대화 상태 모델

- `thread_id`, `session_id`, actor/tenant, current intent/entities
- unresolved slots/ambiguities
- approved facts/evidence IDs와 valid time
- workflow state/checkpoint pointer
- rolling summary와 summary version
- recent turns limited window
- retrieved relevant history references

### 6.2 필요한 대화만 선택하는 메모리 흐름

최근 2~4 turn + 구조화 state + relevant history retrieval + 갱신된 summary만 전달한다. 전체 대화는 기본적으로 다시 보내지 않는다. 주문번호/상품/날짜 같은 live entity는 source 재조회 후 사용한다.

| Exp | Baseline | Variant | Metrics | 채택 기준 |
|---|---|---|---|---|
| MEM-01 | full transcript | recent N + summary | task accuracy, contradiction, token, latency | 품질 허용범위 내 token 절감 |
| MEM-02 | recent only | relevant history retrieval | entity carryover F1, wrong-memory rate | 오래된 관련 turn 회수 개선 |
| MEM-03 | stateless retry | LangGraph checkpoint resume | completion, duplicate tool calls, recovery time | duplicate side effect 0, resume 성공 |

Long-term 고객 선호는 현 Core 범위에서 필요성이 낮고 PII/동의 부담이 크므로 기본 비활성화한다. 상품/운영의 장기 문맥은 고객 Memory가 아니라 Canonical DB/Retrieval로 관리한다.

## 7. 소형 언어모델과 QLoRA 미세조정

### 7.1 적용 대상 업무

1. Inquiry intent/entity/risk/lookup flag structured extraction
2. 짧은 운영 지시의 Task/Event JSON extraction

생성형 CS 답변 전체를 QLoRA 목표로 두지 않는다. 최신 상품·재고·정책은 Retrieval이 책임지고, sLLM은 안정적인 구조화와 routing에 집중한다.

### 7.2 학습 지시 형식

```json
{
  "messages": [
    {"role": "system", "content": "commerce NLU policy + schema"},
    {"role": "user", "content": "sanitized input"},
    {"role": "assistant", "content": "canonical JSON"}
  ],
  "metadata": {"task": "inquiry_nlu", "language": "ko", "source": "synthetic|real|public"}
}
```

### 7.3 학습 설정 탐색 범위

| Parameter | 후보 | 선택 근거 |
|---|---|---|
| Base model | 1개 주모델. 주모델이 목표 GPU VRAM을 초과하거나 배포 허용 License를 충족하지 못할 때만 작은 대안 1개 | Korean structured output, license, VRAM, serving latency |
| Quantization | 4-bit NF4 QLoRA vs base/LoRA feasible baseline | 메모리/품질 trade-off |
| Rank/Alpha | r 8/16/32, alpha r 또는 2r | capacity와 overfit 비교 |
| LR | 5e-5, 1e-4, 2e-4 | validation loss/F1 안정성 |
| Epoch/Step | 1~5 epoch 또는 fixed step | early stopping/checkpoint eval |
| Batch | per-device + grad accumulation으로 effective 16/32 | VRAM과 gradient 안정성 |
| Target modules | 1차 attention projection. Validation Intent Macro F1이 Base 대비 2%p 미만 개선이면서 train/validation gap이 5%p 이하일 때만 MLP 포함 후보 1회 추가 | 최소 adapter로 품질 확보 |
| Scheduler/Warmup | cosine/linear, 3~10% | 작은 dataset 안정성 |

모든 조합의 전수검색은 하지 않는다. 작은 pilot에서 LR/rank를 좁히고 상위 checkpoint만 정식 Eval한다.

### 7.4 QLoRA 비교실험

| 단계 | 비교 | Metric/진단 |
|---|---|---|
| FT-00 | Large API LLM structured prompt baseline | 품질 상한/비용/latency |
| FT-01 | Base sLLM zero/few-shot | fine-tuning 전 기준 |
| FT-02 | QLoRA rank/LR pilot | validation loss, F1, valid rate, overfit gap |
| FT-03 | checkpoint별 동일 Test | Intent/Entity F1, Exact/Field, JSON Valid, latency |
| FT-04 | imbalance strategy | minority F1, false positive, calibration |
| FT-05 | quantized serving | memory, throughput, p50/p95, cost |

Checkpoint는 training loss 최저가 아니라 Validation/Test의 task metric과 calibration으로 선택한다. Train/Test near duplicate, 특정 brand memorization, rare class hallucination, JSON truncation을 Error Analysis한다.

### 7.5 채택 기준

- QLoRA가 Base보다 Intent/Entity 또는 JSON Valid에서 실질 개선되고 serving budget을 만족해야 한다.
- Large API와 품질 차이가 작은 routine class에서 cost/latency 이점이 있어야 한다.
- 특정 slice가 불안정하면 router가 Large/Human으로 승격한다.
- 개선이 없으면 Base+Prompt 또는 API model을 채택하고 QLoRA는 `REJECTED_WITH_EVIDENCE`로 남긴다.

## 8. 그래프와 그래프 기반 검색

### 8.1 개체와 관계

| Entity | 핵심 ID | 주요 Relation |
|---|---|---|
| Brand | brand_id | HAS_PRODUCT |
| Product/SKU | product_id/sku_id | VARIANT_OF, BASE_GAME_OF, EXPANSION_OF, CONTAINS, COMPATIBLE_WITH |
| Order/Reservation | order_id | CONTAINS_SKU, RESERVES, FULFILLED_BY |
| Inquiry/Return | inquiry_id/return_id | ABOUT_PRODUCT, CAUSED_BY_ISSUE |
| IncomingStock | incoming_id | SUPPLIES, EXPECTED_AT |
| LaunchEvent/Task | event_id/task_id | LAUNCHES, DEPENDS_ON, BLOCKS, AFFECTED_BY |

### 8.2 같은 개체 판별과 중복 처리

Provider ID exact mapping → normalized SKU/barcode/alias rule → candidate retrieval → human decision 순서다. 합쳐진 entity에는 alias, provenance, valid time, confidence, resolver version을 저장한다. 충돌 entity는 별도 유지하며 Graph edge를 자동 생성하지 않는다.

### 8.3 그래프가 필요한 질문

- “이 확장팩을 단독 플레이 가능한가?”: Base/Expansion/Compatibility multi-hop
- “예약주문을 지연시키는 입고와 출시 Task는?”: Reservation→SKU→Incoming→Launch→Task traversal
- “문의와 반품이 함께 증가한 같은 상품/구성품?”: Product 중심 multi-relation aggregation

단일 SKU 재고, 주문 상태, exact 상품 조회는 SQL이 더 명확하므로 GraphRAG를 사용하지 않는다.

### 8.4 그래프 비교실험 GRAPH-01

| 비교 | Query Slice | Metrics | 비용/복잡도 | 결정 |
|---|---|---|---|---|
| SQL joins | exact/known schema | answer/path accuracy, latency | baseline | PENDING |
| Hybrid RAG | 자연어/설명 | Recall, groundedness | index 운영 | PENDING |
| Graph traversal | multi-hop relation | path recall, answer accuracy | projection 관리 | PENDING |
| Graph + Vector | entity가 모호한 multi-hop | entity/path/answer | 가장 복잡 | 명확한 이점 있을 때만 |

Graph DB 채택은 relation query의 정확도/latency/maintainability가 PostgreSQL relation baseline보다 실질적으로 좋을 때만 한다. 그렇지 않으면 relational projection+recursive query를 유지한다.

## 9. LangGraph 운영 에이전트

### 9.1 적용 경계

예약주문 lifecycle, 출시 일정 재계획, multi-turn CS처럼 상태·분기·HITL·중단복구가 필요한 Workflow에만 사용한다. 단일 분류/검색/재고 계산은 일반 함수/API로 구현한다.

### 9.2 명시적 상태 스키마

```text
AgentState
  workflow_id, thread_id, tenant_id, schema_version
  trigger_event_ids[], current_node, status
  task_type, risk_level, confidence
  entities{}, evidence_ids[], source_as_of
  rule_results{}, retrieval_result{}, model_result{}
  proposed_actions[], approval_state
  tool_receipts[], retry_count{}, deadlines{}
  errors[], audit_ids[], next_allowed_nodes[]
```

### 9.3 단계와 조건 분기

이벤트 검증 → 확정 규칙 → 추가 문맥 필요 여부 → 검색/그래프 → 신뢰도·모델 선택 → 제안 생성 → 안전 확인 → 사람 승인 또는 제안 저장 → 완료. 각 분기는 명시적 사유 코드를 기록한다.

### 9.4 신뢰성 설계

- checkpoint: node 완료 후 state+output hash 저장
- retry: transient error만 bounded exponential backoff; validation/policy error는 retry하지 않음
- timeout: tool별 deadline; timeout 후 receipt/status 조회
- idempotent tool: `tenant+workflow+action+target+version` key
- failure recovery: DLQ/manual queue와 last safe checkpoint resume
- HITL: approve/reject/edit/expire, actor/policy/audit
- state resume: code/schema migration 가능 version
- model routing: low confidence만 상위 모델
- audit: input hash, tool args/result, prompt/model/version, transition reason

### 9.5 에이전트 비교실험

| 실험 | 실패 주입/비교 | 평가 지표 | 통과 조건 |
|---|---|---|---|
| AG-01 | DB/API timeout at each node | recovery rate, completion time | 상태 유실 0 |
| AG-02 | duplicate event/tool retry | duplicate side effect | 0 |
| AG-03 | low confidence/stale evidence | correct human route | 100% safety slice |
| AG-04 | checkpoint resume vs restart | repeated calls/token/recovery | duplicate tool 0, token 감소 |
| AG-05 | 대형모델 직접 에이전트 vs 단계형 모델 선택기 | 품질, 호출수, 토큰, 지연 | 단계형 방식이 품질 조건을 유지하며 비용 절감 |

## 10. 재고와 운영 분석

### 10.1 초기 모델

데이터가 SKU 2,000+에 비해 판매 1,100+ 수준으로 희소할 수 있으므로 딥러닝 forecast를 핵심으로 두지 않는다.

```text
available = on_hand - reserved_confirmed
net_need = max(0, reservation_demand + safety_stock - available - confirmed_incoming)
risk_features = sales_velocity, acceleration, days_of_cover, lead_time,
                reservation_aging, incoming_delay, data_freshness, mapping_confidence
```

Rule priority baseline과 weighted risk ranking을 비교하고, 충분한 history가 있는 brand/category/SKU slice에서만 naive seasonal/rolling mean 또는 tree-based ranking baseline을 검토한다.

### 10.2 운영 분석 비교실험

| 비교 | 목표 | Metric | 채택 원칙 |
|---|---|---|---|
| fixed rule vs weighted ranking | 오늘의 Task 우선순위 | Precision@N, missed critical, operator agreement | critical miss를 늘리지 않는 범위 |
| naive velocity vs simple ML | stockout risk | PR-AUC, recall at alert budget, calibration | time-split에서 안정적일 때만 |
| SKU vs category fallback | sparse SKU | error/coverage | 데이터 적은 SKU는 pooled baseline |

AI 설명은 계산값을 바꾸지 않고 feature contribution과 source를 자연어로 제시한다.

## 11. 모델 선택과 토큰 비용

### 11.1 모델 선택 정책

```text
deterministic available? -> Rule/SQL (0 LLM)
structured routine task + sLLM confidence >= threshold -> sLLM
grounded short answer + low risk -> small/low-cost LLM
complex/multi-source + confidence gap -> large LLM
high risk/stale/unsupported -> human, no autonomous action
```

### 11.2 측정 항목

각 request에 route, reason, model, prompt version, input/output/cache tokens, latency, estimated cost, cache hit, quality/safety outcome를 기록한다.

| Exp | Baseline | Variant | Metrics | Result |
|---|---|---|---|---|
| ROUTE-01 | Large LLM Only | staged router | cost/request, avg token, p95, quality, safety | PENDING |
| ROUTE-02 | no cache | retrieval/semantic cache | hit rate, stale hit, cost, latency | PENDING |
| ROUTE-03 | fixed threshold | calibrated confidence | large call rate, error, abstain | PENDING |

목표는 Large-only 대비 비용 절감이지만 절감률을 미리 성과로 선언하지 않는다. 품질/Safety Gate를 통과한 가장 저렴한 route를 채택한다.

## 12. 평가 목록과 결과 기록

### 12.1 실험 결과 기록 형식

```yaml
experiment_id: RAG-03
hypothesis: ...
dataset_manifest: sha256:...
split_version: v1
code_commit: ...
config: ...
seed: ...
baseline: ...
metrics: {...}
latency_cost: {...}
slice_results: {...}
error_samples: [...]
decision: PENDING|ADOPTED|REJECTED|CONDITIONAL
decision_reason: ...
artifacts: [...]
```

### 12.2 공통 오류 분류

- entity miss/wrong link/ambiguous mapping
- intent confusion/rare class
- invalid JSON/missing field
- retrieval miss/filter error/stale source/duplicate context
- unsupported claim/citation mismatch
- graph entity/path error
- agent wrong route/retry loop/duplicate tool
- memory contradiction/stale remembered fact
- budget/latency regression
- safety policy miss

### 12.3 채택·기각 판단 규칙

1. Safety regression이 있으면 기각
2. 사전 정의 품질 조건 미달이면 기각하거나 조건부 경로로 제한
3. 전체 평균뿐 아니라 critical slice를 통과해야 함
4. 통계적/실질적 개선과 latency/cost trade-off를 함께 평가
5. 동률이면 단순하고 운영하기 쉬운 방식 선택
6. 실제 결과는 `09` 절차로 검증 후 이 문서/Experiment Registry에 기록

## 13. 사용하지 않을 수 있는 기법과 설명

| 기법 | 미사용/제한 조건 | 설명 가능 문장 |
|---|---|---|
| Multi-query | exact SKU/짧은 query에서 false expansion·비용 증가 | 복합/모호 query에만 conditional 사용 |
| Context overlap | record duplication만 늘고 Recall 개선 없음 | structure-aware record가 경계를 보존 |
| Long-term customer memory | 동의/PII 부담 대비 필요성 낮음 | 운영 데이터와 thread state로 충분 |
| Graph DB | SQL/projection이 동일 품질·더 단순 | Graph가 필요한 multi-hop에만 적용 |
| GraphRAG | relation path가 답에 기여하지 않는 query | 단일 재고/주문은 SQL이 정확 |
| ReAct | 단일 lookup/classification | 도구 선택·관찰 반복이 필요한 Agent에만 |
| QLoRA | Base/API 대비 개선 또는 비용 이점 없음 | 실패 결과도 포트폴리오 evidence |
| Deep forecast | SKU별 history 부족 | Rule/statistical baseline과 time-split부터 |
| Large LLM per event | 비용/latency/불필요한 변동성 | Rule/sLLM/router로 제한 |

## 14. 21일 AI 완료 조건

- Prompt, Retrieval, QLoRA, Graph, Memory, Agent, Routing 실험의 결과가 최소 1개 이상의 재현 가능한 run으로 기록됨
- BM25/Vector/Hybrid/Reranker 비교표와 query-slice error analysis 존재
- Base/QLoRA/Large baseline 비교와 checkpoint 선택 근거 존재
- Agent failure injection, checkpoint resume, HITL, duplicate tool test 통과
- Large-only vs Router cost/token/latency benchmark 존재
- 채택하지 않은 기술도 `REJECTED/CONDITIONAL` 이유가 존재
- Metric이 없는 기능은 `완료`가 아니라 `PENDING EVALUATION`
