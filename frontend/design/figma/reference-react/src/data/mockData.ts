// 합성 데모 데이터 — 실제 개인정보, 매장 식별자, 자격증명 없음
// Final field names come from OpenAPI/JSON Schema contract

export type Env = "demo" | "production";

export const ENV: Env = "demo";

export type ProviderStatus = "ok" | "degraded" | "error" | "stale";

export interface Provider {
  id: string;
  name: string;
  status: ProviderStatus;
  lastSync: string;
  latencyMs: number;
  note?: string;
}

export const providers: Provider[] = [
  { id: "cafe24", name: "Cafe24", status: "ok", lastSync: "2분 전", latencyMs: 142 },
  { id: "toss", name: "Toss POS", status: "ok", lastSync: "5분 전", latencyMs: 87 },
  { id: "ecount", name: "eCount", status: "stale", lastSync: "47분 전", latencyMs: 0, note: "API 응답 지연" },
];

export interface RiskItem {
  id: string;
  type: "재고불일치" | "예약부족" | "입고지연" | "문의위험" | "매핑모호";
  severity: "critical" | "warning";
  title: string;
  description: string;
  product?: string;
  sku?: string;
  affectedCount?: number;
  confidence?: number;
  sources: string[];
  asOf: string;
  evidence?: EvidenceItem[];
}

export interface EvidenceItem {
  id: string;
  type: "rule" | "ai" | "human";
  label: string;
  value: string;
  source: string;
  asOf: string;
}

export const riskItems: RiskItem[] = [
  {
    id: "r001",
    type: "재고불일치",
    severity: "critical",
    title: "재고 수량 불일치 감지",
    description: "Cafe24 진열재고(12개)와 eCount 실재고(3개) 간 9개 차이 발생. 과판매 위험.",
    product: "레드벨벳 케이크 (500g)",
    sku: "CAKE-RV-500",
    affectedCount: 9,
    confidence: 97,
    sources: ["Cafe24", "eCount"],
    asOf: "3분 전",
    evidence: [
      { id: "e1", type: "rule", label: "Cafe24 진열재고", value: "12개", source: "Cafe24 상품관리 API", asOf: "3분 전" },
      { id: "e2", type: "rule", label: "eCount 실재고", value: "3개", source: "eCount 재고조회 API", asOf: "47분 전" },
      { id: "e3", type: "ai", label: "AI 판단", value: "eCount 데이터가 47분 전으로 지연됨. 실재고 3개 기준 과판매 위험도 높음.", source: "AI 분석 엔진 v2.3", asOf: "3분 전" },
    ],
  },
  {
    id: "r002",
    type: "예약부족",
    severity: "critical",
    title: "주말 예약 수량 부족",
    description: "9/7(토) 예약 주문 24개, 현재 확보 재료로 18개 생산 가능. 6개 충족 불가.",
    product: "티라미수 케이크 세트",
    sku: "CAKE-TM-SET",
    affectedCount: 6,
    confidence: 91,
    sources: ["Cafe24", "eCount"],
    asOf: "12분 전",
    evidence: [
      { id: "e4", type: "rule", label: "예약 주문 수", value: "24개 (9/7 배송)", source: "Cafe24 주문 API", asOf: "12분 전" },
      { id: "e5", type: "rule", label: "생산 가능 수량", value: "18개", source: "eCount 원자재 재고", asOf: "47분 전" },
      { id: "e6", type: "ai", label: "부족 예측", value: "6개 미충족. 고객 6명 배송 불가 예상. 대체 입고 또는 취소 안내 필요.", source: "AI 분석 엔진 v2.3", asOf: "12분 전" },
    ],
  },
  {
    id: "r003",
    type: "입고지연",
    severity: "warning",
    title: "원자재 입고 지연 — 생크림",
    description: "예정 입고일 9/4, 공급사 통보 지연 9/7. 9/5~6 생산 스케줄 영향 가능.",
    affectedCount: 3,
    confidence: 85,
    sources: ["eCount"],
    asOf: "1시간 전",
  },
  {
    id: "r004",
    type: "문의위험",
    severity: "warning",
    title: "문의 급증 — 배송 지연",
    description: "오늘 오후 배송지연 관련 문의 23건 (전일 대비 +340%). AI 초안 대기 중.",
    affectedCount: 23,
    confidence: 88,
    sources: ["Cafe24"],
    asOf: "8분 전",
  },
  {
    id: "r005",
    type: "매핑모호",
    severity: "warning",
    title: "상품 매핑 모호 — 3건",
    description: "Cafe24 신규 상품 3개가 eCount 품목과 자동 매핑 실패. 수동 검토 필요.",
    affectedCount: 3,
    confidence: 62,
    sources: ["Cafe24", "eCount"],
    asOf: "2시간 전",
  },
];

export interface KPIData {
  label: string;
  value: string;
  sub?: string;
  trend?: "up" | "down" | "flat";
  trendValue?: string;
  source: string;
  asOf: string;
  status?: "ok" | "warn" | "crit";
}

export const kpiData: KPIData[] = [
  { label: "오늘 총 주문", value: "247건", sub: "₩3,842,000", trend: "up", trendValue: "+12%", source: "Cafe24 + Toss POS", asOf: "5분 전", status: "ok" },
  { label: "온라인 주문", value: "189건", sub: "₩2,910,000", trend: "up", trendValue: "+8%", source: "Cafe24", asOf: "2분 전", status: "ok" },
  { label: "오프라인 매출", value: "58건", sub: "₩932,000", trend: "down", trendValue: "-3%", source: "Toss POS", asOf: "5분 전", status: "ok" },
  { label: "재고 위험 SKU", value: "7개", sub: "즉시 조치 필요 3개", source: "eCount", asOf: "47분 전", status: "crit" },
  { label: "미처리 문의", value: "31건", sub: "AI 초안 대기 14건", source: "Cafe24", asOf: "8분 전", status: "warn" },
  { label: "오늘 AI 처리", value: "128건", sub: "정확도 92.4%", source: "AI 분석 엔진", asOf: "1분 전", status: "ok" },
];

export interface ProductRow {
  id: string;
  name: string;
  sku: string;
  cafe24Stock: number;
  ecountStock: number;
  diff: number;
  incoming: number;
  incomingDate?: string;
  status: "ok" | "warn" | "crit" | "stale";
  lastUpdated: string;
  price: string;
}

export const products: ProductRow[] = [
  { id: "p001", name: "레드벨벳 케이크 500g", sku: "CAKE-RV-500", cafe24Stock: 12, ecountStock: 3, diff: -9, incoming: 20, incomingDate: "9/6", status: "crit", lastUpdated: "3분 전", price: "₩42,000" },
  { id: "p002", name: "티라미수 케이크 세트", sku: "CAKE-TM-SET", cafe24Stock: 24, ecountStock: 18, diff: -6, incoming: 30, incomingDate: "9/8", status: "crit", lastUpdated: "12분 전", price: "₩58,000" },
  { id: "p003", name: "딸기 생크림 케이크", sku: "CAKE-STR-WC", cafe24Stock: 15, ecountStock: 15, diff: 0, incoming: 0, status: "ok", lastUpdated: "5분 전", price: "₩38,000" },
  { id: "p004", name: "초코 가나슈 롤케이크", sku: "ROLL-CHO-GAN", cafe24Stock: 8, ecountStock: 6, diff: -2, incoming: 10, incomingDate: "9/5", status: "warn", lastUpdated: "47분 전", price: "₩28,000" },
  { id: "p005", name: "얼그레이 생크림 케이크", sku: "CAKE-EG-WC", cafe24Stock: 20, ecountStock: 20, diff: 0, incoming: 0, status: "ok", lastUpdated: "5분 전", price: "₩45,000" },
  { id: "p006", name: "말차 라떼 케이크", sku: "CAKE-MT-LAT", cafe24Stock: 5, ecountStock: 0, diff: -5, incoming: 15, incomingDate: "9/7", status: "crit", lastUpdated: "47분 전", price: "₩48,000" },
  { id: "p007", name: "시즌 한정 복숭아 케이크", sku: "CAKE-PEACH-LTD", cafe24Stock: 30, ecountStock: 28, diff: -2, incoming: 0, status: "warn", lastUpdated: "47분 전", price: "₩52,000" },
];

export interface OrderRow {
  id: string;
  orderId: string;
  customer: string;
  product: string;
  qty: number;
  amount: string;
  source: "Cafe24" | "Toss POS";
  status: "완료" | "준비중" | "배송중" | "취소" | "보류";
  deliveryDate?: string;
  orderedAt: string;
  riskFlag?: string;
}

export const orders: OrderRow[] = [
  { id: "o001", orderId: "C24-20240904-8821", customer: "데모고객 001", product: "레드벨벳 케이크 500g", qty: 1, amount: "₩42,000", source: "Cafe24", status: "준비중", deliveryDate: "9/6", orderedAt: "오늘 09:14", riskFlag: "재고부족" },
  { id: "o002", orderId: "C24-20240904-8820", customer: "데모고객 002", product: "티라미수 케이크 세트 x2", qty: 2, amount: "₩116,000", source: "Cafe24", status: "준비중", deliveryDate: "9/7", orderedAt: "오늘 09:02" },
  { id: "o003", orderId: "TP-20240904-1043", customer: "현장방문 고객", product: "딸기 생크림 케이크", qty: 1, amount: "₩38,000", source: "Toss POS", status: "완료", orderedAt: "오늘 10:30" },
  { id: "o004", orderId: "C24-20240904-8819", customer: "데모고객 003", product: "말차 라떼 케이크", qty: 1, amount: "₩48,000", source: "Cafe24", status: "보류", deliveryDate: "9/7", orderedAt: "어제 18:41", riskFlag: "재고없음" },
  { id: "o005", orderId: "C24-20240904-8818", customer: "데모고객 004", product: "얼그레이 생크림 케이크", qty: 1, amount: "₩45,000", source: "Cafe24", status: "배송중", deliveryDate: "9/5", orderedAt: "어제 16:22" },
  { id: "o006", orderId: "TP-20240904-1042", customer: "현장방문 고객", product: "초코 가나슈 롤케이크", qty: 2, amount: "₩56,000", source: "Toss POS", status: "완료", orderedAt: "오늘 10:15" },
  { id: "o007", orderId: "C24-20240904-8817", customer: "데모고객 005", product: "시즌 한정 복숭아 케이크", qty: 1, amount: "₩52,000", source: "Cafe24", status: "준비중", deliveryDate: "9/6", orderedAt: "어제 15:10" },
];

export interface InquiryRow {
  id: string;
  ticketId: string;
  customer: string;
  subject: string;
  intent: string;
  entities: string[];
  confidence: number;
  draftStatus: "대기" | "초안완료" | "검토중" | "발송완료" | "보류";
  urgency: "높음" | "보통" | "낮음";
  source: string;
  receivedAt: string;
  draftText?: string;
  citations?: string[];
}

export const inquiries: InquiryRow[] = [
  {
    id: "q001",
    ticketId: "INQ-20240904-0231",
    customer: "데모고객 001",
    subject: "주문한 케이크 배송이 언제 되나요?",
    intent: "배송조회",
    entities: ["주문번호: C24-20240904-8821", "상품: 레드벨벳 케이크"],
    confidence: 96,
    draftStatus: "초안완료",
    urgency: "높음",
    source: "Cafe24 1:1문의",
    receivedAt: "10분 전",
    draftText: "안녕하세요, 고객님. 주문하신 레드벨벳 케이크 500g의 배송 현황을 안내드립니다.\n\n현재 제품 준비 중이며, 예정 배송일은 9월 6일(금)입니다. 배송 시작 시 문자로 운송장 번호를 안내드릴 예정입니다.\n\n불편을 드려 죄송합니다. 추가 문의 사항이 있으시면 언제든지 연락 주세요.",
    citations: ["주문 상태: 준비중", "배송 예정일: 9월 6일", "상품: 레드벨벳 케이크 500g", "배송 정책: 출고 후 평균 2~3영업일"],
  },
  {
    id: "q002",
    ticketId: "INQ-20240904-0230",
    customer: "데모고객 003",
    subject: "케이크 픽업 날짜 변경 가능한가요?",
    intent: "일정변경",
    entities: ["주문번호: C24-20240904-8819", "변경 요청일: 9/8"],
    confidence: 88,
    draftStatus: "검토중",
    urgency: "보통",
    source: "Cafe24 1:1문의",
    receivedAt: "25분 전",
    draftText: "안녕하세요, 고객님. 픽업 날짜 변경 요청 주셨습니다.\n\n요청하신 9월 8일(일) 픽업으로 변경 가능합니다. 단, 재고 확인 후 최종 확정 안내드리겠습니다.",
    citations: ["운영 정책: 픽업 변경 48시간 전 가능", "말차 라떼 케이크 재고: 0개 (9/7 입고 예정)", "관련 정책: 예약 상품은 입고 후 순차 발송"],
  },
  {
    id: "q003",
    ticketId: "INQ-20240904-0229",
    customer: "데모고객 002",
    subject: "알레르기 성분 확인 부탁드립니다",
    intent: "상품정보",
    entities: ["상품: 티라미수 케이크 세트", "알레르기: 글루텐"],
    confidence: 93,
    draftStatus: "초안완료",
    urgency: "높음",
    source: "Cafe24 1:1문의",
    receivedAt: "1시간 전",
    citations: ["상품 성분: 티라미수 케이크 - 글루텐 함유(밀 포함)", "알레르기 안내: 유제품, 달걀, 밀 포함"],
  },
  {
    id: "q004",
    ticketId: "INQ-20240904-0228",
    customer: "데모고객 004",
    subject: "환불 요청합니다",
    intent: "환불요청",
    entities: ["주문번호: C24-20240904-8818"],
    confidence: 72,
    draftStatus: "보류",
    urgency: "높음",
    source: "Cafe24 1:1문의",
    receivedAt: "2시간 전",
    draftText: "환불 관련 요청이 접수되었습니다. 정책에 따라 배송 전 취소 또는 수령 후 7일 이내 반품이 가능합니다.\n\n[AI 판단 신뢰도 낮음 — 담당자가 직접 확인 후 답변해 주세요]",
    citations: ["주문 상태: 배송중", "환불 정책: 배송 전 전액 환불 가능 / 수령 후 7일 이내 반품 가능", "주의: 배송 진행 중으로 담당자 확인 필요"],
  },
];

export interface ScheduleItem {
  id: string;
  date: string;
  time: string;
  type: "생산" | "배송" | "입고" | "픽업" | "점검";
  title: string;
  status: "예정" | "진행중" | "완료" | "지연" | "취소";
  note?: string;
  isProposal?: boolean;
  originalDate?: string;
}

export const scheduleItems: ScheduleItem[] = [
  { id: "s001", date: "9/4 (수)", time: "08:00", type: "생산", title: "오전 생산 배치 — 레드벨벳 12개", status: "완료" },
  { id: "s002", date: "9/4 (수)", time: "11:00", type: "입고", title: "생크림 원자재 입고", status: "지연", note: "공급사 통보: 9/7로 변경" },
  { id: "s003", date: "9/4 (수)", time: "14:00", type: "배송", title: "오후 배송 출고 — 32건", status: "진행중" },
  { id: "s004", date: "9/5 (목)", time: "08:00", type: "생산", title: "오전 생산 배치 — 티라미수 18개", status: "예정", note: "⚠ 원자재 부족 가능" },
  { id: "s005", date: "9/5 (목)", time: "09:00", type: "픽업", title: "이*준 고객 픽업 (말차 케이크)", status: "예정", note: "재고 0개 — 입고 후 가능" },
  { id: "s006", date: "9/6 (금)", time: "10:00", type: "배송", title: "주말 예약 배송 출고 1차", status: "예정" },
  { id: "s007", date: "9/7 (토)", time: "08:00", type: "입고", title: "생크림 원자재 입고 (변경)", status: "예정", isProposal: true, originalDate: "9/4" },
  { id: "s008", date: "9/7 (토)", time: "10:00", type: "배송", title: "주말 예약 배송 출고 2차 — 24건", status: "예정", note: "⚠ 6건 미충족 예상" },
];

export interface MappingCandidate {
  id: string;
  cafe24Name: string;
  cafe24Sku: string;
  candidates: { ecountCode: string; ecountName: string; similarity: number; source: string }[];
  status: "미검토" | "승인" | "거부" | "수동지정";
}

export const mappingCandidates: MappingCandidate[] = [
  {
    id: "m001",
    cafe24Name: "복숭아 무스 케이크 (신제품)",
    cafe24Sku: "CAKE-PEACH-MO",
    candidates: [
      { ecountCode: "RM-PEACH-001", ecountName: "복숭아 무스 원형 케이크", similarity: 84, source: "BM25 텍스트 유사도" },
      { ecountCode: "RM-PEACH-002", ecountName: "복숭아 생크림 케이크", similarity: 71, source: "BM25 텍스트 유사도" },
    ],
    status: "미검토",
  },
  {
    id: "m002",
    cafe24Name: "블루베리 크림치즈 타르트 6구",
    cafe24Sku: "TART-BB-CC-6",
    candidates: [
      { ecountCode: "RM-TART-BB-6", ecountName: "블루베리 타르트 6개입", similarity: 79, source: "BM25 텍스트 유사도" },
      { ecountCode: "RM-TART-BB-4", ecountName: "블루베리 타르트 4개입", similarity: 61, source: "BM25 텍스트 유사도" },
    ],
    status: "미검토",
  },
  {
    id: "m003",
    cafe24Name: "제주 녹차 롤케이크",
    cafe24Sku: "ROLL-JJ-GT",
    candidates: [
      { ecountCode: "RM-ROLL-GT", ecountName: "녹차 롤케이크", similarity: 76, source: "BM25 텍스트 유사도" },
      { ecountCode: "RM-ROLL-MT", ecountName: "말차 롤케이크", similarity: 68, source: "BM25 텍스트 유사도" },
    ],
    status: "미검토",
  },
];

export interface AIInsight {
  id: string;
  type: "재고예측" | "수요분석" | "가격최적화" | "문의분류";
  title: string;
  summary: string;
  confidence: number;
  model: string;
  generatedAt: string;
  feedback?: "긍정" | "부정";
  tags: string[];
}

export const aiInsights: AIInsight[] = [
  { id: "ai001", type: "재고예측", title: "주말 재고 소진 예측", summary: "이번 주 토요일까지 레드벨벳, 말차 케이크 재고 완전 소진 예측. 긴급 추가 생산 또는 판매 제한 검토 권장.", confidence: 91, model: "ops-forecast-v2.3", generatedAt: "10분 전", tags: ["재고", "예측", "주말"] },
  { id: "ai002", type: "수요분석", title: "추석 시즌 수요 급증 예상", summary: "9/14~17 추석 연휴 기준 전년 동기 대비 +180% 주문 예상. 선물 세트 재고 사전 확보 필요.", confidence: 87, model: "ops-forecast-v2.3", generatedAt: "1시간 전", tags: ["추석", "시즌", "수요"] },
  { id: "ai003", type: "문의분류", title: "배송 지연 문의 클러스터 감지", summary: "오늘 오후 동일 배송지역(강남구) 배송 지연 문의 23건 집중. 단일 사유(물류 지연) 가능성 높음.", confidence: 88, model: "inquiry-cls-v1.8", generatedAt: "8분 전", tags: ["문의", "배송", "클러스터"] },
];
