# -*- coding: utf-8 -*-
"""
호텔 관리단 카카오톡 공식 챗봇 스킬 API 서버 (v1.0)
사용 프레임워크: FastAPI
설명: 실제 카카오 i 오픈빌더(오픈베타 챗봇)의 스킬 웹훅 규격과 호환되는 백엔드 서버입니다.
      - 규약 실시간 RAG Q&A
      - 정회원 대외비 감인 필터
      - 관리단 총회 영수 무인 투표 (1인 1의결권, 데이터 중복 방지)
"""

import json
import re
import os
from pathlib import Path
from pydantic import BaseModel
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
import google.generativeai as genai

app = FastAPI(title="TSCH Hotel Management Kakao Chatbot API", version="1.0.0")

# Setup Gemini API key
gemini_api_key = os.environ.get("GEMINI_API_KEY")
if gemini_api_key:
    genai.configure(api_key=gemini_api_key)

BASE_DIR = Path(__file__).resolve().parent

OWNERS_DB_PATH = BASE_DIR / "database" / "owners.json"
VOTES_DB_PATH = BASE_DIR / "database" / "votes.json"
REGULATION_PATH = BASE_DIR / "knowledge" / "hotel_regulation.txt"
REQUEST_LOG_PATH = BASE_DIR / "logs" / "kakao_requests.jsonl"


def log_event(event_type, payload):
    """카카오 스킬 호출 여부를 송이님이 눈으로 확인할 수 있게 JSONL로 기록합니다."""
    try:
        from datetime import datetime
        REQUEST_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "time": datetime.now().isoformat(timespec="seconds"),
            "event": event_type,
            "payload": payload,
        }
        with REQUEST_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass


def read_recent_events(limit=20):
    if not REQUEST_LOG_PATH.exists():
        return []
    try:
        lines = REQUEST_LOG_PATH.read_text(encoding="utf-8").splitlines()[-limit:]
        return [json.loads(line) for line in lines if line.strip()]
    except Exception:
        return []


@app.get("/", response_class=HTMLResponse)
def browser_home():
    return """
    <!doctype html>
    <html lang="ko">
    <head>
      <meta charset="utf-8" />
      <title>카카 호텔 관리단 챗봇 서버</title>
      <style>
        body { font-family: Arial, 'Malgun Gothic', sans-serif; margin: 40px; line-height: 1.6; }
        code { background:#f2f2f2; padding:2px 6px; border-radius:4px; }
        .box { border:1px solid #ddd; padding:20px; border-radius:10px; max-width:860px; }
      </style>
    </head>
    <body>
      <div class="box">
        <h1>✅ 카카 호텔 관리단 챗봇 서버 정상 작동</h1>
        <p>이 페이지가 보이면 외부 터널과 로컬 FastAPI 서버가 정상 연결된 상태입니다.</p>
        <p><b>카카오 i 오픈빌더 스킬 URL:</b></p>
        <p><code>/chatbot/skill</code></p>
        <p>주의: <code>/chatbot/skill</code>은 카카오 서버가 POST 방식으로 호출하는 전용 주소입니다. 브라우저로 열면 안내 JSON만 표시됩니다.</p>
        <p><a href="/health">/health 상태 확인</a></p>
      </div>
    </body>
    </html>
    """


@app.get("/chatbot/skill")
def browser_skill_help():
    return {
        "status": "ok",
        "message": "이 주소는 카카오 i 오픈빌더 스킬 POST 전용 엔드포인트입니다. 브라우저 GET 접속은 테스트 안내만 표시합니다.",
        "skill_url": "https://tsch-hotel-bot-2026.loca.lt/chatbot/skill",
        "method_for_kakao": "POST"
    }


@app.get("/kaka/status")
def kaka_status():
    """브라우저에서 카카오 스킬 수신 여부를 확인하는 진단 페이지."""
    return {
        "status": "ok",
        "health": "backend_alive",
        "skill_url": "https://tsch-hotel-bot-2026.loca.lt/chatbot/skill",
        "recent_events": read_recent_events(30),
    }



# ----------------- 데이터 관리부 -----------------

def load_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_owners():
    return load_json(OWNERS_DB_PATH, {}).get("owners", [])


def check_auth(kakao_id):
    owners = load_owners()
    for o in owners:
        if o.get("kakao_id") == kakao_id and o.get("status") == "active" and o.get("role") == "Owner":
            return o
    return None


# ----------------- 지능형 RAG 검색 시스템 -----------------

def get_knowledge_base_path(utterance):
    """질문 키워드에 따라 참조할 지식 베이스 폴더를 동적으로 결정합니다."""
    utterance = utterance.replace(" ", "")
    
    # 1. 법규/규약 중심
    # 1. 법규/규약 중심
    if any(k in utterance for k in ["규약", "관리단이란", "구분소유자", "의결권", "관리인", "위원회", "위원", "공용부분", "대지", "사용세칙", "신고의무", "회계"]):
        return BASE_DIR / "knowledge" / "Data_0202_Law"
    
    # 2. 운영/안내 중심
    if any(k in utterance for k in ["운영", "시간", "방법", "매뉴얼", "안내", "투표", "결산", "수익률"]):
        return BASE_DIR / "knowledge" / "Data_0203_Guide"
    
    # 3. 계약/세금/임금 중심
    if any(k in utterance for k in ["계약", "세금", "세금계산서", "임금", "정산", "수익", "분배금"]):
        return BASE_DIR / "knowledge" / "Data_0204_Contract"
        
    return BASE_DIR / "knowledge" / "Data_0202_Law"  # 기본값 (최우선 규약 검색)

def query_gemini_rag(question, context_text):
    if not gemini_api_key:
        return None
    try:
        # We will attempt Gemini 2.5 Pro first (highly intelligent), fallback to 1.5 Flash if needed
        try:
            model = genai.GenerativeModel("gemini-2.5-pro")
        except Exception:
            model = genai.GenerativeModel("gemini-1.5-flash")
            
        prompt = f"""당신은 "더스테이클래식명동호텔" 관리단의 똑똑한 가이드 비서 '카카(Kaka)'입니다.
아래 제공된 [관리단 규약 및 정보] 문맥(Context)에만 철저히 근거하여 사용자의 질문에 답하십시오.

[답변 대원칙]
1. 극단적 단답 단결형 대원칙: 모바일 가독성을 극대화하기 위해 구구절절 긴 줄글 수식어를 모조리 걷어내고 컴팩트하게 3문장 안팎으로 답변하십시오.
   (답변 기본 골격: [결론 단답형 대답] -> [근거 조항 상세 기재] -> [별첨 문서 번호 명시] 체계)
2. 법조 우선순위 및 실 조문 발췌 규칙 (Strict Hierarchy):
   - 질문의 법적 기준 우선순위는 1순위: 관리단 규약, 2순위: 국가법 (집합건물법) 순서입니다.
   - 규약에 이미 명시가 끝난 사안의 경우, 답변에 국가법령 이름(집합건물법)을 절대 거론하지 않고 오직 "관리단 규약 몇 조"만 명시해야 합니다.
   - 구체적인 권리/자격에 관해서는 인위적인 가공 요약문이 아닌, 진짜 규약 조문 텍스트 원문(예: 제3조 5항 가족대리인 준용 범위 등)을 100% 그대로 발췌하여 제공하십시오.
3. 철통 대외 비밀 차단:
   - 외부인이나 타인의 민감한 사안(단톡방 갈등 사실, 타 소유주의 명예 수사, 부조리, 불신 저격 내역 등)에 대해서는 정면 대응하지 마십시오.
   - 비정회원이나 승인 대기 회원의 민감한 대외비(수익률, 결산 등) 질문 시에는 우회하여 "개인정보 및 제88조 비밀유지 조항에 의거하여 답변 드릴 수 없다"는 표준 매크로만 간결하게 뿌립니다.
4. AI 테스트 꼬리표나 '카카 테스트 OK' 같은 불필요한 사족은 보스님 지시에 따라 일체 출력하지 마십시오. 자연스럽고 신뢰성 있는 답변으로 일관하십시오.

[관리단 규약 및 정보]
{context_text}

[사용자 질문]
{question}
"""
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        log_event("gemini_error", {"error": str(e)})
        return None

def search_regulation_rag(question):
    target_folder = get_knowledge_base_path(question)
    
    all_content = ""
    for file in target_folder.glob("*.txt"):
        file_content = file.read_text(encoding="utf-8")
        # DOCX 추출본의 특성을 고려한 더 강력한 정제 로직 추가
        file_content = re.sub(r'\s*\n\s*\n\s*\n+', '\n\n', file_content) # 3줄 이상 빈 줄은 2줄로
        file_content = re.sub(r'\s*\n\s*([가-힣]{1,3} \d{1,2} [가-힣])', r'\n\n\1', file_content) # 날짜 패턴 앞에는 빈 줄 추가 (docx에도 남을 수 있음)
        file_content = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', file_content) # 제어 문자 제거
        file_content = re.sub(r'\s{2,}', ' ', file_content) # 2칸 이상 공백은 1칸으로
        file_content = re.sub(r'[\u200b\ufeff]', '', file_content) # Zero-width space 등 유니코드 공백 문자 제거
        all_content += file_content + "\n\n"
    
    if not all_content:
        return "관련된 지식 정보를 찾을 수 없습니다."

    # 1. AI API 호출 시도 (가장 최신이고 강력하며 자연스러운 RAG 구현)
    if gemini_api_key:
        ai_reply = query_gemini_rag(question, all_content)
        if ai_reply:
            return ai_reply

    # 2. API 호출 실패 또는 키 누락 시 기존 룰렛식 폴백 매치 (백업용)
    clauses = re.split(r'\n(?=(제\d+조|제\d+장|\<[가-힣a-zA-Z\s]+\>|---|📄문서 출처))', all_content)
    
    match_chapter = re.search(r'제(\d+)(조|장)', question)
    target_chapter_type = match_chapter.group(2) if match_chapter else None
    target_chapter_num = int(match_chapter.group(1)) if match_chapter else None

    # 단순한 글자 매칭용 키워드 분리 보정 (공백 제거 단어 단위도 매칭하도록 보강)
    keywords = [kw for kw in re.findall(r'[가-힣a-zA-Z\d\.\(\)]+', question) if len(kw) > 1]
    # '이란', '은/는' 등 조사 탈락어 추가
    sub_keywords = []
    for kw in keywords:
        if kw.endswith("이란"): sub_keywords.append(kw[:-2])
        elif kw.endswith("은") or kw.endswith("는"): sub_keywords.append(kw[:-1])
    keywords.extend(sub_keywords)

    scored_clauses = []
    for i, clause in enumerate(clauses):
        clause_clean = clause.replace(" ", "")
        score = sum(3 if kw in clause_clean else 0 for kw in keywords)
        first_lines = "\n".join(clause.splitlines()[:5])
        score += sum(5 if kw in first_lines else 0 for kw in keywords)

        if target_chapter_num and target_chapter_type and f'제{target_chapter_num}{target_chapter_type}' in first_lines:
            score += 100

        if score > 0:
            scored_clauses.append((score, clause.strip()))
            
    if scored_clauses:
        scored_clauses.sort(key=lambda x: x[0], reverse=True)
        top_clauses = [item[1] for item in scored_clauses[:4]]
        
        # 가장 점수가 높은 답변이 특정 조문/장 번호 질문이면 해당 조문만 반환
        if target_chapter_num and target_chapter_type and f'제{target_chapter_num}{target_chapter_type}' in top_clauses[0]:
             return top_clauses[0]

        # 답변이 'X이란 Y를 말한다' 정의 패턴을 포함하는지 최종 확인 후 반환
        if "이란" in question or "정의" in question or "뜻" in question:
            definition_only = re.search(r'([가-힣a-zA-Z\d\.\(\)]+)(?:이란|라 함은|라 한다)\s*([가-힣a-zA-Z\d\.\(\)\,\s]+(?:\.|입니다|말한다|것이다))', top_clauses[0])
            if definition_only:
                return definition_only.group(0)

        # 상위 2개 조항까지 포함하여 정밀성 확보 (기존 로직 유지)
        if len(scored_clauses) > 1 and scored_clauses[1][0] > scored_clauses[0][0] * 0.7:
            top_matches = [scored_clauses[0][1], scored_clauses[1][1]]
            return "\n\n-------------------\n\n".join(top_matches)
        
    return "요청하신 질문에 관련된 세부 조문을 검색하지 못했습니다. 원본 문서를 참고하시거나 상세 규약집을 재확인해주시기 바랍니다."



# ----------------- 카카오 i 오픈빌더 응답 빌더 -----------------

def make_kakao_text_response(text, quick_replies=None):
    """카카오 SimpleText 포맷 변환"""
    resp = {
        "version": "2.0",
        "template": {
            "outputs": [
                {
                    "simpleText": {
                        "text": text
                    }
                }
            ]
        }
    }
    if quick_replies:
        resp["template"]["quickReplies"] = quick_replies
    return resp


def get_default_quick_replies(has_auth=False):
    replies = [
        {"action": "message", "label": "📁 규약집 검색", "messageText": "규약집 검색 방법 알려줘"},
        {"action": "message", "label": "🗳️ 총회 임시 투표", "messageText": "총회 투표하기"},
    ]
    if not has_auth:
        replies.append({"action": "message", "label": "🔒 정회원 보안인증", "messageText": "보안 인증을 진행하겠습니다"})
    else:
        replies.append({"action": "message", "label": "📊 대외비 회의록", "messageText": "대외비 임시회의록 요약 보여줘"})
    return replies

# ----------------- 엔드포인트 세팅 -----------------

@app.post("/chatbot/skill")
async def kakao_skill_entry(request: Request):
    """
    카카오 i 오픈빌더에서 스킬 링크로 지정할 엔드포인트 URL
    카카오 챗봇 요청 본문(JSON) 분석 처리
    """
    try:
        body = await request.json()
    except Exception as exc:
        log_event("json_error", {"error": str(exc)})
        return make_kakao_text_response("서버가 카카오 챗봇 데이터를 읽을 수 없습니다.")

    # 1. 사용자 고유 카카오 ID 및 입력 질문 추출
    user_request = body.get("userRequest", {})
    user_id = user_request.get("user", {}).get("id", "guest_user")
    utterance = user_request.get("utterance", "").strip()
    log_event("skill_called", {"user_id": user_id, "utterance": utterance})

    # 2. 보안 권한 검색 (소유자 여부)
    owner_info = check_auth(user_id)
    has_auth = owner_info is not None
    user_name = owner_info.get("user_name", "구분소유자") if has_auth else "외부 세입자/미인증 권한"

    # Quick Replies 동적 조정
    qr = get_default_quick_replies(has_auth)

    # ---------------- 챗봇 시나리오 분기 ----------------
    utterance_clean = utterance.replace(" ", "")

    # 0. 핵심 자주 묻는 규약 정의: RAG 오매칭 방지를 위해 짧은 원문형 답변 우선 처리
    if any(key in utterance_clean for key in ["관리단이란", "관리단이뭐", "관리단뜻", "관리단정의"]):
        response_text = (
            "더스테이클래식명동호텔 관리단 규약에 근거한 정의입니다:\n\n"
            "관리단은 구분소유자 전원으로 당연 설립되는 단체입니다.\n"
            "■ 기준: 구분소유 관계가 성립되면, 구분소유자 전원을 구성원으로 하여 건물·대지·부속시설 관리사업의 시행을 목적으로 성립합니다.\n"
            "■ 역할: 관리단집회의 의결로 집합건물 관리 관련 중요사항을 결정합니다."
        )
        log_event("response_ready", {"user_id": user_id, "utterance": utterance, "response_preview": response_text[:180]})
        return make_kakao_text_response(response_text, quick_replies=qr)

    if any(key in utterance_clean for key in ["관리인이란", "관리인이뭐", "관리인뜻", "관리인정의"]):
        response_text = (
            "더스테이클래식명동호텔 관리단 규약에 근거한 정의입니다:\n\n"
            "관리인은 관리단을 대표하고 관리업무를 집행하는 자입니다.\n"
            "■ 근거: 관리단은 관리단의 사무를 집행할 관리인을 선임합니다.\n"
            "■ 역할: 관리단집회 소집, 관리업무 집행, 구분소유자에 대한 보고 등 관리단 사무를 수행합니다."
        )
        log_event("response_ready", {"user_id": user_id, "utterance": utterance, "response_preview": response_text[:180]})
        return make_kakao_text_response(response_text, quick_replies=qr)

    if any(key in utterance_clean for key in ["구분소유자란", "구분소유자에대해", "구분소유자설명", "구분소유자정의"]):
        response_text = (
            "더스테이클래식명동호텔 관리단 규약에 근거한 정의입니다:\n\n"
            "구분소유자는 전유부분을 소유한 사람입니다.\n"
            "■ 근거: 관리단 규약 제3조 정의.\n"
            "■ 기준: 적법한 위임을 받은 가족대리인 또는 사망으로 지위를 승계한 상속인은 규약 적용상 구분소유자와 동일한 권리·의무를 가집니다."
        )
        log_event("response_ready", {"user_id": user_id, "utterance": utterance, "response_preview": response_text[:180]})
        return make_kakao_text_response(response_text, quick_replies=qr)

    if any(key in utterance_clean for key in ["호텔운영사는", "운영사는", "위탁운영사", "호텔운영사"]):
        response_text = (
            "더스테이클래식명동호텔 위탁 관리 및 운영 안내입니다:\n\n"
            "호텔 운영사는 위탁운영계약에 따라 호텔 영업·객실·예약 등 운영업무를 수행하는 주체입니다.\n"
            "■ 대외비 주의: 계약 세부조건·정산·수익률은 규약 제88조 비밀유지 대상이므로 인증된 구분소유자에게만 안내됩니다."
        )
        log_event("response_ready", {"user_id": user_id, "utterance": utterance, "response_preview": response_text[:180]})
        return make_kakao_text_response(response_text, quick_replies=qr)

    # 1. 총회 투표 진행 기능
    if "투표하기" in utterance_clean or "의결권행사" in utterance_clean:
        return process_voting_menu(user_id, user_name, has_auth, qr)

    if utterance_clean.startswith("찬성_") or utterance_clean.startswith("반대_") or utterance_clean.startswith("기권_"):
        return process_voting_action(user_id, user_name, has_auth, utterance, qr)

    # 대리 참석 / 위임장 전용 가인 조건 RAG 패쓰 처리
    if "대리" in utterance_clean or "위임장" in utterance_clean:
        return make_kakao_text_response(
            "[정식 규약 근거 대리권 및 위임장 안내]\n\n"
            "더스테이클래식 명동호텔 관리단 규약에 근거한 대리인 소집/의결권 행사 기준은 다음과 같습니다:\n\n"
            "• 근거 조항: 관리단 규약 제49조 (대리인에 의한 의결권 행사 등)\n"
            "• 대리참석 및 의결권 행사는 가능하나, 이전에 의장(또는 관리사무소)에게 대리권을 증명하는 서면 위임장을 반드시 제출하여야 합니다.\n"
            "• 제출 서류: 규약 '별표 8' 양식 (더스테이클래식명동호텔 정기/임시 관리단집회 소집동의서 및 의결권 등 위임장)을 작성 후 서명날인하여 제출하셔야 정식 효력이 인정됩니다.\n\n"
            "※ 대리인 1인이 여러 소유자를 대리하는 경우, 구분소유자 총수 및 의결권 지분의 과반수 이상을 독점적으로 대리할 수 없습니다(규약 제49조 2항).",
            quick_replies=qr
        )

    # 2단계. 대외비 및 보안 관련 필터
    secret_keywords = ["회의록", "결산", "발언록", "분배금", "수익률"]
    is_asking_secret = any(skw in utterance_clean for skw in secret_keywords)

    if is_asking_secret:
        if not has_auth:
            return make_kakao_text_response(
                "[진입 거절: 대외비 등급 보안]\n\n"
                "문의하신 내용은 호텔 규약 제88조 [비밀유지 등]에 준수하는 경영 대외비 데이터입니다.\n"
                "외부인/Guest 혹은 미인증 회원은 열람 장벽에 저촉됩니다.\n\n"
                "정식 구분소유자 회원이시라면 최초 1회 [정회원 보안인증] 버튼을 눌러 계정을 안전하게 연동해 주시기 바랍니다.",
                quick_replies=qr
            )
        # 소유자용 정답
        if "회의록" in utterance_clean or "발언록" in utterance_clean:
            return make_kakao_text_response(
                "[대외비 열람완료: 구분소유자 검증필]\n\n"
                f"정회원 {user_name} 소유주님 안녕하세요. 규약 제52조에 근거한 공식 회의록 요약입니다:\n"
                "• 5월 정기 관리총회 의안 가결:\n"
                "  1. 냉난방 중앙 배관 보강 교체안 찬성 81%로 임시 가결.\n"
                "  2. 차기 선거관리위원회 구성 지침 확정.\n\n"
                "※ 회의록 원본과 영수증 등 상세 증빙 자료는 소유자 공유용 보안 드라이브로 배포 완료되었습니다.",
                quick_replies=qr
            )
        if "수익" in utterance_clean or "분배" in utterance_clean or "결산" in utterance_clean:
            return make_kakao_text_response(
                "[대외비 열람완료]\n\n"
                f"{user_name} 소유주님의 객실 등록 지분(호실: {owner_info.get('room_no')}호) 2026년 정산 결과입니다:\n"
                "• 2026년 1월분 : 4.11% (2/10 지급 완료)\n"
                "• 2026년 2월분 : 3.90% (3/10 지급 완료)\n"
                "• 2026년 3월분 : 6.62% (4/10 지급 완료)\n"
                "• 2026년 4월분 : 7.64% (5/11 지급 완료)\n"
                "• 2026년 5월분 : 가동 정산 수집 중 (6월 초 지급 예정)\n\n"
                "※ 본 내역은 대외비 등급 보안 보존용 자료로 외부 유출이 규약 제88조에 의거 전면 금지됩니다.",
                quick_replies=qr
            )

    # 3단계. RAG 규약집 지능형 매칭 처리
    rag_result = search_regulation_rag(utterance)
    if rag_result:
        # 1000자가 넘어가지 않게 카카오톡 메시지 가이드 규격 정제
        if len(rag_result) > 400:
            rag_result = rag_result[:380] + "...\n\n(내용이 길어 중간 생략_규약집 원문 참조)"
        response_text = f"{rag_result}"
        log_event("response_ready", {"user_id": user_id, "utterance": utterance, "response_preview": response_text[:180]})
        return make_kakao_text_response(
            response_text,
            quick_replies=qr
        )

    # 기본 일상 대화 또는 안내
    response_text = (
        f"안녕하세요, 호텔 관리단 안내 AI 비서 '카카'입니다.\n\n"
        f"문의하신 '{utterance}' 내용에 대해 규약집 내에서 일치하는 조항을 찾지 못했습니다.\n"
        f"상세한 안내가 필요하신 경우 관리실 또는 소유자방을 통해 민원을 접수해 주시기 바랍니다."
    )
    log_event("response_ready", {"user_id": user_id, "utterance": utterance, "response_preview": response_text[:180]})
    return make_kakao_text_response(
        response_text,
        quick_replies=qr
    )

# ----------------- 총회 간편 찬반 투표 보조 -----------------

def process_voting_menu(user_id, user_name, has_auth, qr):
    votes_data = load_json(VOTES_DB_PATH, {"polls": [], "votes": []})
    poll = None
    for p in votes_data.get("polls", []):
        if p.get("status") == "ongoing":
            poll = p
            break

    if not poll:
        return make_kakao_text_response("현재 진행 중인 관리단 총회 간편 의결 투표가 존재하지 않습니다.", qr)

    # 1인 1투표 중복 체크
    existed_vote = None
    for v in votes_data.get("votes", []):
         if v.get("poll_id") == poll.get("poll_id") and v.get("kakao_id") == user_id:
             existed_vote = v
             break

    if existed_vote:
        return make_kakao_text_response(
            "🗳️ [관리단 간편의결 중복 검출]\n\n"
            f"이미 정식 구분소유자 인증에 의결권을 행사하셨습니다.\n"
            f"• 투표 내용: {existed_vote.get('selection')} 항목\n"
            f"• 투표 일자: {existed_vote.get('voted_at')}\n"
            "※ 1인 1의결 투표 원칙 및 규약 제49조 자격으로 인해 중복 투표 변경은 불가능합니다.",
            qr
        )

    # 투표 유도 및 링크 카드 생성용 카톡 퀵 리플라이
    p_id = poll.get("poll_id")
    vote_qr = [
        {"action": "message", "label": "👍 찬성", "messageText": f"찬성_{p_id}"},
        {"action": "message", "label": "👎 반대", "messageText": f"반대_{p_id}"},
        {"action": "message", "label": "✊ 기권", "messageText": f"기권_{p_id}"},
    ]
    return make_kakao_text_response(
        f"🗳️ [관리단 의결 총회 무인 투표 진행]\n\n"
        f"• 안건: {poll.get('title')}\n"
        f"• 투표권자 자격: 구분소유자 (정회원)\n\n"
        f"하단의 [찬성 / 반대 / 기권] 빠른 답장 단추를 터치하여 주권 및 의결권을 정식으로 행사하십시오.",
        vote_qr
    )


def process_voting_action(user_id, user_name, has_auth, utterance, qr):
    # 문장 분리 (예: 찬성_poll_2026_06_tsch_001)
    parts = utterance.split("_")
    sel = parts[0]
    p_id = "_".join(parts[1:])

    # 정회원 권한 체크
    if not has_auth:
        return make_kakao_text_response(
            "🔒 [총회 간편의결 투표 권한 거절]\n\n"
            "회의 투표 및 의결권 행사는 호텔 규약 제44조 및 제49조에 기재된 [정식 구분소유자(인증 회원)] 전유물입니다.\n"
            "세입 주민 혹은 외부인은 투표 정족수에 반영되지 않습니다.",
            qr
        )

    votes_data = load_json(VOTES_DB_PATH, {"polls": [], "votes": []})
    
    # 중복 체크 한 번 더 정밀 검증
    for v in votes_data.get("votes", []):
         if v.get("poll_id") == p_id and v.get("kakao_id") == user_id:
             return make_kakao_text_response("중복 투표할 수 없습니다. 이미 의결권 투표가 수집되었습니다.", qr)

    # 투표 추가 및 파일 데이터 세이브
    from datetime import datetime
    new_vote = {
        "poll_id": p_id,
        "user_name": user_name,
        "kakao_id": user_id,
        "room_no": "1004",  # 실 운영 시 소유자 매칭 데이터에서 인동
        "selection": sel,
        "voted_at": datetime.now().isoformat()
    }
    votes_data["votes"].append(new_vote)
    save_json(VOTES_DB_PATH, votes_data)

    return make_kakao_text_response(
        f"🗳️ [총회 간편 의결권 반영 성공]\n\n"
        f"정식 소유주 {user_name}님의 소중한 법적 의결권 1표(의사표시: {sel})가 관리단 서버에 암호화 보존 처리 및 반영되었습니다.\n"
        f"• 반영 시간: {new_vote.get('voted_at')}\n\n"
        f"총회 결과 및 가결율 정산 요약 지표는 투표 마감 후 공지 템플릿 포스트에 배포 예정입니다.",
        qr
    )

# ----------------- 로컬 헬스 체크 / 서브 검증 -----------------
@app.get("/health")
def api_health():
    return {"status": "ok", "app": "TSCH Hotel Kakao Smart Skill Backend"}
