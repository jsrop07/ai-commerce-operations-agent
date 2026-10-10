"""기존 로컬 프로젝트에 최소 범위로 적용하는 운영 AI 1차 패치.
Windows CMD: python apply_operator_ai_phase1.py C:\\ai-commerce-operations-agent
파일 일치 여부를 검사하고 .bak 복사본을 남깁니다.
"""
from pathlib import Path
import sys
import shutil

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
backend = root / 'backend/app/services/conversation_v2.py'
frontend = root / 'frontend/src/components/CommonAiDrawer.tsx'

def require_replace(text, old, new, tag):
    if old not in text:
        raise RuntimeError(f'[{tag}] 기존 코드가 일치하지 않아 중단했습니다. 파일을 덮어쓰지 않았습니다.')
    if text.count(old) != 1:
        raise RuntimeError(f'[{tag}] 대상 위치가 여러 개여서 중단했습니다.')
    return text.replace(old, new, 1)

original_b = backend.read_text(encoding='utf-8')
original_f = frontend.read_text(encoding='utf-8')
b = original_b
f = original_f

# 1. 예약 질문을 '재고' 또는 '주문' 키워드로 잘못 라우팅하지 않음.
anchor = '    if any(word in text for word in ("재고", "품절", "가용수량", "가용 수량")):'
insert = '''    # 예약 물량 질문은 단순 판매 추세나 재고 Snapshot 질문으로 오분류하지 않습니다.
    # 검증된 DB 기반 예약 계산 어댑터가 질문 Runtime에 연결되기 전까지 HOLD 처리합니다.
    if any(word in text for word in ("예약", "미확보", "확보 수량", "예약 물량")):
        return "DETERMINISTIC", "RESERVATION_REVIEW"

'''
b = require_replace(b, anchor, insert + anchor, 'reservation classification')

old = 'if question_type in {"INVENTORY_UNAVAILABLE", "UNSUPPORTED"}:'
new = 'if question_type in {"INVENTORY_UNAVAILABLE", "UNSUPPORTED", "RESERVATION_REVIEW"}:'
b = require_replace(b, old, new, 'hold routing')
# 단일 분기 앞에 새로운 안전 HOLD 분기를 추가합니다.
old = '            else:\n                conclusion = (\n                    "현재 질문은 지원되는 운영 분석 범위에 "'
new = '''            elif question_type == "RESERVATION_REVIEW":
                conclusion = (
                    "예약 수량은 현재 대화에서 검증된 계산 결과를 "
                    "가져오지 못해 충분 여부를 판단할 수 없습니다."
                )
                next_check = (
                    "운영 일정에서 예약 필요 수량, 현재 확보 수량, "
                    "입고 예정 수량과 조건부 잔여를 확인해 주세요."
                )
            else:
                conclusion = (
                    "현재 질문은 지원되는 운영 분석 범위에 "'''
b = require_replace(b, old, new, 'reservation hold body')

old = '"최근 10일 유효수량: "'
b = require_replace(b, old, '"최근 10일 유효 주문 수량: "', 'recent label')
old = '"직전 10일 유효수량: "'
b = require_replace(b, old, '"직전 10일 유효 주문 수량: "', 'previous label')
old = '"품질상태: {aggregate.quality_status}"'
b = require_replace(b, old, '"주문 데이터 확인 상태: {aggregate.quality_status}"', 'quality label')

# 2. 운영자용 패널의 분석 모드 선택과 원클릭 분석 버튼은 UI에서만 제거.
import re
# 들여쓰기와 JSX 줄바꿈이 달라도 정확한 두 UI 블록만 탐지합니다.
mode_pattern = re.compile(
    r'(?P<indent>^[ \t]*)\{isEntity\s*&&\s*displayContext\.targetType\s*===\s*"PRODUCT"\s*&&\s*\('
    r'\s*<label>분석 방식\s*<select\b[\s\S]*?aria-label="분석 방식"[\s\S]*?</select>\s*</label>\s*\)\}',
    re.M,
)
button_pattern = re.compile(
    r'^[ \t]*\{isEntity\s*&&\s*displayContext\.targetType\s*===\s*"PRODUCT"\s*&&'
    r'\s*<button\b[^>]*onClick=\{\(\)\s*=>\s*void\s+runAnalysis\(\)\}[^>]*>'
    r'분석 실행</button>\}', re.M,
)
mode_matches = list(mode_pattern.finditer(f))
button_matches = list(button_pattern.finditer(f))
if len(mode_matches) != 1 or len(button_matches) != 1:
    raise RuntimeError(f'[mode controls] 분석 선택 UI {len(mode_matches)}건, 실행 버튼 {len(button_matches)}건 확인. 소스 불일치로 중단합니다.')
f = mode_pattern.sub('', f, count=1)
f = button_pattern.sub('', f, count=1)

f = require_replace(f,
    'const [analysisKind, setAnalysisKind] = useState<AnalysisKind>("DETERMINISTIC");',
    'const [analysisKind] = useState<AnalysisKind>("DETERMINISTIC");', 'mode state')
f = require_replace(f,
    '    setAnalysisKind("DETERMINISTIC");',
    '    // 분석 모드는 사용자에게 노출하지 않고 자연어 질문에 따라 서버에서 결정합니다.', 'mode reset')
# 미사용 지역 변수 제거: 일부 컴파일러 noUnusedLocals 검사 대응.
import re
f, cleanup_count = re.subn(r'^[ \t]*const canAnalyze\s*=\s*isEntity\s*&&\s*displayContext\.targetType\s*===\s*"PRODUCT"\s*&&\s*sessionState\s*===\s*"ready"\s*&&\s*!busy\s*&&\s*!pendingTransition\s*;[ \t]*\n?', '', f, flags=re.M)
if cleanup_count != 1:
    raise RuntimeError('[canAnalyze] 위치가 일치하지 않습니다.')

# 3. 보기 쉬운 기본 설명: 기술적 사실은 근거 보기/서버 데이터에 보존.
old = 'return publicMode ? content.split("\\n").filter((line) => !line.startsWith("근거:")).join("\\n") : content;'
new = '''return publicMode
    ? content.split("\\n").filter((line) => !line.startsWith("근거:")).map((line) => {
        if (!line.startsWith("핵심 수치/상태:")) return line;
        return line.replace(/; (?:데이터 모드|기준시각|상품번호|품질상태|주문 데이터 확인 상태): [^;]*/g, "");
      }).join("\\n")
    : content;'''
f = require_replace(f, old, new, 'public display')

# 모든 변경 패턴이 검증된 다음에만 두 파일 쓰기.
for path, original, updated in ((backend, original_b, b), (frontend, original_f, f)):
    backup = path.with_suffix(path.suffix + '.pre-operator-ai.bak')
    if backup.exists():
        raise RuntimeError(f'기존 백업이 있어 중단: {backup}')
for path, original, updated in ((backend, original_b, b), (frontend, original_f, f)):
    backup = path.with_suffix(path.suffix + '.pre-operator-ai.bak')
    shutil.copy2(path, backup)
    path.write_text(updated, encoding='utf-8')
    print(f'PATCHED {path}\nBACKUP  {backup}')
print('완료: 대화 분류/표시만 변경. DB, LLM Provider, Graph, Conversation 저장 계약 미변경.')
