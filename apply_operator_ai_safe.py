"""운영 AI 안전 패치: 실행 전 코드 구조 확인, --check 미리보기, --apply 적용.
Windows CMD: python apply_operator_ai_safe.py --check C:\\ai-commerce-operations-agent
"""
from __future__ import annotations
import argparse
import difflib
import re
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('root', type=Path)
p.add_argument('--check', action='store_true')
p.add_argument('--apply', action='store_true')
args = p.parse_args()
if args.check == args.apply:
    p.error('--check 또는 --apply 중 하나만 지정하세요')
paths = [args.root/'backend/app/services/conversation_v2.py', args.root/'frontend/src/components/CommonAiDrawer.tsx']
originals = [x.read_text(encoding='utf-8') for x in paths]
b, f = originals

def replace_once(s, old, new, name):
    matches=s.count(old)
    if matches!=1:
        raise RuntimeError(f'{name}: 예상 1곳, 실제 {matches}곳. 파일 수정 안 함')
    return s.replace(old,new,1)

# 예약 질문은 상품 주문량이나 실재고로 오분류하지 않는다. 예약 계산 연결 이전엔 HOLD.
anchor='    if any(word in text for word in ("재고", "품절", "가용수량", "가용 수량")):'
addition='''    # 예약은 주문 추세/재고 스냅샷과 다른 근거를 사용합니다.
    if any(word in text for word in ("예약", "미확보", "확보 수량")):
        return "DETERMINISTIC", "RESERVATION_REVIEW"

'''
b=replace_once(b,anchor,addition+anchor,'예약 분류')
b=replace_once(b,'if question_type in {"INVENTORY_UNAVAILABLE", "UNSUPPORTED"}:',
'''if question_type in {"INVENTORY_UNAVAILABLE", "UNSUPPORTED", "RESERVATION_REVIEW"}:''','HOLD 분기')
old='''            else:
                conclusion = (
                    "현재 질문은 지원되는 운영 분석 범위에 "'''
new='''            elif question_type == "RESERVATION_REVIEW":
                conclusion = (
                    "예약 부족 여부는 이 대화의 검증된 예약 계산 근거가 연결되지 않아 판단을 보류합니다."
                )
                next_check = "운영 일정에서 현재 미확보 수량과 예정 입고 반영 후 조건부 잔여를 확인하세요."
            else:
                conclusion = (
                    "현재 질문은 지원되는 운영 분석 범위에 "'''
b=replace_once(b,old,new,'예약 HOLD 답변')
b=replace_once(b,'"최근 10일 유효수량: "','"최근 10일 유효 주문 수량: "','최근 10일 용어')
b=replace_once(b,'"직전 10일 유효수량: "','"직전 10일 유효 주문 수량: "','직전 10일 용어')

# 분석 모드 선택 UI와 직접 실행 버튼만 제거. 자연어 전송은 그대로 보존.
# 정확한 JSX 경계로 블록을 찾고, 내용을 검증한 다음에만 삭제한다.
start_marker='{isEntity && displayContext.targetType === "PRODUCT" && ('
starts=[m.start() for m in re.finditer(re.escape(start_marker),f)]
mode_candidates=[]
for pos in starts:
    end=f.find('</label>',pos)
    if end<0: continue
    block=f[pos:end+len('</label>')]
    if '<label>분석 방식' in block and 'aria-label="분석 방식"' in block and '<select' in block:
        close=re.match(r'\s*\)\}',f[end+len('</label>'):])
        if close:
            mode_candidates.append((pos,end+len('</label>')+close.end()))
if len(mode_candidates)!=1:
    raise RuntimeError(f'분석 방식 UI: 예상 1곳, 실제 {len(mode_candidates)}곳. 파일 수정 안 함')
a,z=mode_candidates[0]
f=f[:a]+f[z:]
button_pattern=re.compile(r'\{isEntity\s*&&\s*displayContext\.targetType\s*===\s*"PRODUCT"\s*&&\s*<button\b[^>]*\bonClick=\{\(\)\s*=>\s*void\s+runAnalysis\(\)\}[^>]*>\s*분석 실행\s*</button>\}',re.S)
button_matches=list(button_pattern.finditer(f))
if len(button_matches)!=1:
    raise RuntimeError(f'분석 실행 버튼: 예상 1곳, 실제 {len(button_matches)}곳. 파일 수정 안 함')
f=button_pattern.sub('',f,count=1)
# 버튼을 제거했으므로 내부 모드 state 및 사용하지 않는 변수만 안전하게 정리한다.
f=replace_once(f,'const [analysisKind, setAnalysisKind] = useState<AnalysisKind>("DETERMINISTIC");',
                'const analysisKind: AnalysisKind = "DETERMINISTIC";','내부 기본 모드')
f=replace_once(f,'    setAnalysisKind("DETERMINISTIC");','    // 분석 방식은 질문 API에서 서버가 선택합니다.','모드 초기화')
f,count=re.subn(r'^[ \t]*const canAnalyze\s*=\s*isEntity\s*&&\s*displayContext\.targetType\s*===\s*"PRODUCT"\s*&&\s*sessionState\s*===\s*"ready"\s*&&\s*!busy\s*&&\s*!pendingTransition;[ \t]*\r?\n','',f,flags=re.M)
if count!=1: raise RuntimeError(f'canAnalyze: 예상 1곳 실제 {count}곳. 파일 수정 안 함')
# 근거 원문은 그대로 보존하고 일반 사용자에게 용어만 숨긴다.
needle='return publicMode ? content.split("\\n").filter((line) => !line.startsWith("근거:")).join("\\n") : content;'
replacement='''return publicMode
    ? content.split("\\n").filter((line) => !line.startsWith("근거:")).map((line) => {
        if (!line.startsWith("핵심 수치/상태:")) return line;
        return line.replace(/; (?:데이터 모드|기준시각|상품번호|품질상태): [^;]*/g, "");
      }).join("\\n")
    : content;'''
f=replace_once(f,needle,replacement,'일반 사용자 표시')
if b==originals[0] or f==originals[1]: raise RuntimeError('변경사항 없음')
# 2개 파일 모두 모든 전제 조건 통과 후 쓰기
if args.check:
    for path,orig,updated in zip(paths,originals,[b,f]):
        print(f'\n=== {path} ===')
        print(''.join(difflib.unified_diff(orig.splitlines(True),updated.splitlines(True),fromfile='current',tofile='proposed'))[:9000])
    print('\nCHECK OK: 파일 변경 없음. 실제 DB/Provider 호출 없음.')
else:
    for path in paths:
        backup=path.with_name(path.name+'.operator-ai-original.bak')
        if backup.exists(): raise RuntimeError(f'이미 백업이 존재합니다: {backup} — 원본 수정 안 함')
    for path,orig,updated in zip(paths,originals,[b,f]):
        backup=path.with_name(path.name+'.operator-ai-original.bak')
        backup.write_text(orig,encoding='utf-8')
        path.write_text(updated,encoding='utf-8')
        print('PATCHED:',path,'BACKUP:',backup)
    print('APPLY OK (DB/LLM/Graph 불변). 로컬 빌드·테스트는 별도로 실행하세요.')
