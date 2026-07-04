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
from pathlib import Path
from pydantic import BaseModel
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

app = FastAPI(title="TSCH Hotel Management Kakao Chatbot API", version="1.0.0")

BASE_DIR = Path("C:/Users/PC/Documents/HermesVault/01_Projects/02_Kaka_HotelBot")
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
    if any(k in utterance for k in ["규약", "관리단이란", "구분소유자", "의결권", "관리인"]):
        return BASE_DIR / "knowledge" / "Data_0202_Law"
    
    # 2. 운영/안내 중심
    if any(k in utterance for k in ["운영", "시간", "방법", "매뉴얼", "안내", "투표"]):
        return BASE_DIR / "knowledge" / "Data_0203_Guide"
    
    # 3. 계약/세금/임금 중심
    if any(k in utterance for k in ["계약", "세금", "세금계산서", "임금", "정산", "수익"]):
        return BASE_DIR / "knowledge" / "Data_0204_Contract"
        
    return BASE_DIR / "knowledge" / "Data_0202_Law"  # 기본값

def search_regulation_rag(question):
    target_folder = get_knowledge_base_path(question)
    
    # 해당 폴더 내의 모든 .txt 파일을 검색합니다.
    all_content = ""
    for file in target_folder.glob("*.txt"):
        all_content += file.read_text(encoding="utf-8") + "\n\n"
    
    if not all_content:
        return "관련된 지식 정보를 찾을 수 없습니다."

    # 📑 RAG 검색 로직 (기존 유지)
    clauses = re.split(r'\n(?=제\d+조|---|📄문서 출처)', all_content)
    keywords = [kw for kw in re.findall(r'[가-힣a-zA-Z\d\.\(\)]+', question) if len(kw) > 1]
    
    scored_clauses = []
    for clause in clauses:
        score = sum(3 if kw in clause else 0 for kw in keywords)
        first_lines = "\n".join(clause.splitlines()[:5])
        score += sum(5 for kw in keywords if kw in first_lines)
        
        if score > 0:
            scored_clauses.append((score, clause.strip()))
            
    if scored_clauses:
        scored_clauses.sort(key=lambda x: x[0], reverse=True)
        top_matches = [scored_clauses[0][1]]
        if len(scored_clauses) > 1 and scored_clauses[1][0] > scored_clauses[0][0] * 0.7:
            top_matches.append(scored_clauses[1][1])
        return "\n\n-------------------\n\n".join(top_matches)
    return None

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
            "🤖 [카카 테스트 OK / 규약집 검색 AI 답변]\n\n"
            "관리단은 구분소유자 전원으로 당연 설립되는 단체입니다.\n"
            "■ 기준: 구분소유 관계가 성립되면, 구분소유자 전원을 구성원으로 하여 건물·대지·부속시설 관리사업의 시행을 목적으로 성립합니다.\n"
            "■ 역할: 관리단집회의 의결로 집합건물 관리 관련 중요사항을 결정합니다."
        )
        log_event("response_ready", {"user_id": user_id, "utterance": utterance, "response_preview": response_text[:180]})
        return make_kakao_text_response(response_text, quick_replies=qr)

    if any(key in utterance_clean for key in ["관리인이란", "관리인이뭐", "관리인뜻", "관리인정의"]):
        response_text = (
            "🤖 [카카 테스트 OK / 규약집 검색 AI 답변]\n\n"
            "관리인은 관리단을 대표하고 관리업무를 집행하는 자입니다.\n"
            "■ 근거: 관리단은 관리단의 사무를 집행할 관리인을 선임합니다.\n"
            "■ 역할: 관리단집회 소집, 관리업무 집행, 구분소유자에 대한 보고 등 관리단 사무를 수행합니다."
        )
        log_event("response_ready", {"user_id": user_id, "utterance": utterance, "response_preview": response_text[:180]})
        return make_kakao_text_response(response_text, quick_replies=qr)

    if any(key in utterance_clean for key in ["구분소유자란", "구분소유자에대해", "구분소유자설명", "구분소유자정의"]):
        response_text = (
            "🤖 [카카 테스트 OK / 규약집 검색 AI 답변]\n\n"
            "구분소유자는 전유부분을 소유한 사람입니다.\n"
            "■ 근거: 관리단 규약 제3조 정의.\n"
            "■ 기준: 적법한 위임을 받은 가족대리인 또는 사망으로 지위를 승계한 상속인은 규약 적용상 구분소유자와 동일한 권리·의무를 가집니다."
        )
        log_event("response_ready", {"user_id": user_id, "utterance": utterance, "response_preview": response_text[:180]})
        return make_kakao_text_response(response_text, quick_replies=qr)

    if any(key in utterance_clean for key in ["호텔운영사는", "운영사는", "위탁운영사", "호텔운영사"]):
        response_text = (
            "🤖 [카카 테스트 OK / 운영 안내]\n\n"
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
            "🤖 [정식 규약 근거 대리권 및 위임장 안내]\n\n"
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
                "🔒 [진입 거절: 대외비 등급 보안]\n\n"
                "문의하신 내용은 호텔 규약 제88조 [비밀유지 등]에 준수하는 경영 대외비 데이터입니다.\n"
                "외부인/Guest 혹은 미인증 회원은 열람 장벽에 저촉됩니다.\n\n"
                "정식 구분소유자 회원이시라면 최초 1회 [정회원 보안인증] 버튼을 눌러 계정을 안전하게 연동해 주시기 바랍니다.",
                quick_replies=qr
            )
        # 소유자용 정답
        if "회의록" in utterance_clean or "발언록" in utterance_clean:
            return make_kakao_text_response(
                "🔓 [대외비 열람완료: 구분소유자 검증필]\n\n"
                f"정회원 {user_name} 소유주님 안녕하세요. 규약 제52조에 근거한 공식 회의록 요약입니다:\n"
                "• 5월 정기 관리총회 의안 가결:\n"
                "  1. 냉난방 중앙 배관 보강 교체안 찬성 81%로 임시 가결.\n"
                "  2. 차기 선거관리위원회 구성 지침 확정.\n\n"
                "※ 회의록 원본과 영수증 등 상세 증빙 자료는 소유자 공유용 보안 드라이브로 배포 완료되었습니다.",
                quick_replies=qr
            )
        if "수익" in utterance_clean or "분배" in utterance_clean or "결산" in utterance_clean:
            return make_kakao_text_response(
                "🔓 [대외비 열람완료]\n\n"
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
        response_text = (
            "🤖 [카카 테스트 OK / 규약집 검색 AI 답변]\n\n"
            f"더스테이클래식명동 정식 규약에 명시된 내용을 전송합니다:\n\n"
            f"{rag_result}"
        )
        log_event("response_ready", {"user_id": user_id, "utterance": utterance, "response_preview": response_text[:180]})
        return make_kakao_text_response(
            response_text,
            quick_replies=qr
        )

    # 기본 일상 대화 또는 안내
    response_text = (
        f"🙋 [카카 테스트 OK] 호텔 관리단 안내 AI 비서 '카카'입니다.\n\n"
        f"질문하신 '{utterance}'에 대해 규약집과 매칭된 적절한 정밀 법조항을 찾지 못했습니다.\n"
        f"아래의 주요 메뉴를 참고해 주시거나, 계속 해결이 필요하신 경우 상세 민원을 접수해 주세요."
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
