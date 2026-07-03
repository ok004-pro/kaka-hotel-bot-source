# -*- coding: utf-8 -*-
"""
호텔 관리단 보안 Q&A 챗봇 백엔드 시뮬레이터 (v1.5)
역할: "카카" (Kaka)

실제 hotel_regulation.txt 규약 전문을 탑재한 한 단계 정밀해진 스내치 및 RAG 매칭 시뮬레이터입니다.
"""

import json
import re
from pathlib import Path

BASE_DIR = Path("C:/Users/PC/hotel_bot")
OWNERS_DB_PATH = BASE_DIR / "database" / "owners.json"
REGULATION_PATH = BASE_DIR / "knowledge" / "hotel_regulation.txt"


def load_owners():
    if not OWNERS_DB_PATH.exists():
        return []
    try:
        data = json.loads(OWNERS_DB_PATH.read_text(encoding="utf-8"))
        return data.get("owners", [])
    except Exception:
        return []


def load_regulation():
    if not REGULATION_PATH.exists():
        return ""
    return REGULATION_PATH.read_text(encoding="utf-8")


def check_auth(kakao_id):
    owners = load_owners()
    for owner in owners:
        if owner.get("kakao_id") == kakao_id:
            # 상태가 active이고 소유자(Owner) 역할군인 사람만 인증 정회원으로 우대
            if owner.get("status") == "active" and owner.get("role") == "Owner":
                return owner
    return None


def search_regulation_rag(question):
    raw_regulation = load_regulation()
    if not raw_regulation:
        return "규약집 데이터가 공급되지 않았습니다."

    # 간단한 단락 쪼개기 매칭 (조 단위 분석)
    clauses = re.split(r'\n(?=제\d+조)', raw_regulation)
    keywords = [kw for ln in [question] for kw in re.findall(r'[가-힣a-zA-Z\d]+', ln) if len(kw) > 1]
    
    scored_clauses = []
    for clause in clauses:
        score = sum(1 for kw in keywords if kw in clause)
        if score > 0:
            scored_clauses.append((score, clause.strip()))
            
    if scored_clauses:
        # 가장 연관 점수가 높은 상위 1개 조항을 보여줍니다.
        scored_clauses.sort(key=lambda x: x[0], reverse=True)
        return scored_clauses[0][1]
    return None


def ask_ai(question, has_auth=False):
    question_clean = question.replace(" ", "")

    # 1. 2단계 대외비 민감 단어 확인 필터
    secret_keywords = ["수익률", "분배금", "회의록", "결산", "발언록", "계약서"]
    is_asking_secret = any(skw in question_clean for skw in secret_keywords)

    if is_asking_secret:
        if not has_auth:
            return (
                "🔒 [보안 필터 작동: 대외비 등급 거절]\n"
                "문의하신 내용은 호텔 규약 제88조 [비밀유지 등] 규정에 따라 대외비 보안 자료로 분류되어 있습니다.\n"
                "외부인, 임차인(Guest) 또는 미인증 회원은 열람이 불가합니다. 정식 구분소유자 신분으로 최초 1회 [보안 무인 인증]을 완료하여 주시기 바랍니다."
            )
        
        # 소유자용 보안 정답 매칭
        if "회의록" in question_clean or "발언록" in question_clean:
            return (
                "🔓 [대외비 해제: 정회원 인증성공]\n"
                "회의록 내용(규약 제52조 및 제88조 안내):\n"
                "• 5월 정기대표회의 기록입니다.\n"
                "• 안건: 객실 설비 수선비 정산 충당금 안 및 주차 관리 시스템 연동 승인 완료.\n"
                "• 비고: 회의록 전체 공유용 PDF 드라이브 주소 → https://drive.google.com/drive/folders/xxxx"
            )
        if "수익" in question_clean or "분배" in question_clean:
            return (
                "🔓 [대외비 해제: 정회원 인증성공]\n"
                "수익/운영 통계(규약 제76조, 제83조 안내):\n"
                "• 이번 달 누적 호텔 연간 환산 수익률: 4.85% (안정 수치 유지)\n"
                "• 귀하의 지분 배분 상세 리스트는 안전한 보안 이메일로 별도 우송해 드렸습니다."
            )

    # 2단계 일반 정보에 관한 규약집 검색 (RAG 시뮬레이션)
    rag_result = search_regulation_rag(question)
    if rag_result:
        return (
            "🤖 [규약 RAG 실시간 검색 답변]\n"
            f"송이님이 가지고 계신 정식 규약 조항에서 관련 내용을 찾았습니다:\n\n"
            f"{rag_result}"
        )

    return f"질문인 '{question}'에 맞는 정밀 조항을 분석할 수 없어 원본 규약집 전체 내용을 추가 분석하도록 접수하겠습니다."


def run_test_endpoint(kakao_id, question):
    owner = check_auth(kakao_id)
    user_name = owner.get("user_name", "외부인/비정회원") if owner else "외부인/비정회원"
    role = owner.get("role", "None") if owner else "None"
    has_auth = owner is not None

    print(f"\n==========================================")
    print(f"👤 사용자: {user_name} ({role}) [ID: {kakao_id}]")
    print(f"🔒 보안 권한: {'정회원(열람허용)' if has_auth else '제한대상(열람거부)'}")
    print(f"💬 질문: {question}")
    print(f"------------------------------------------")

    answer = ask_ai(question, has_auth)
    print(f"{answer}")
    print(f"==========================================")


if __name__ == "__main__":
    # 시나리오 테스팅 진행
    # 1. 미인증 외부인(성춘향 - Guest 임차인)이 회의록을 누설을 요구할 때
    run_test_endpoint("user_sung_test_0003", "지난달 회의록 좀 보여주세요")
    
    # 2. 미인증 외부인이라도 일반 법률 투표권 규약은 조회가 가능
    run_test_endpoint("user_sung_test_0003", "전세 투숙객이나 대리인 위임장 투표권 규정")

    # 3. 송이님(정식 소유자 - Owner)이 보안 회의록을 질문할 때
    run_test_endpoint("user_song_dg_tsch_1781", "회의록 안건 정리해 줘")

    # 4. 송이님이 보안 수익 정산과 관련된 조항이나 내용을 물어볼 때
    run_test_endpoint("user_song_dg_tsch_1781", "이번 기수 객실 분배 매출 통계 어떻게 되나요?")
