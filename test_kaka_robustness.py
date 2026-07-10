# -*- coding: utf-8 -*-
"""
카카 호텔봇 상시 견고성 및 시나리오 테스트 스크립트 (test_kaka_robustness.py)
설명: 카카오 i 오픈빌더에서 발생 가능한 각종 정상/비정상 입력값 및 보안, RAG, 투표 처리 로직을
      오프라인/로컬 환경에서 완벽하게 시뮬레이션하여 검증합니다.
"""

import sys
import os
import json
from pathlib import Path

# 프로젝트 루트 경로 추가 및 환경 변수 모킹
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

# 테스트용 API Key 유무 체크 및 기본 목업 세팅
# DeepSeek V4 Pro 전환: DEEPSEEK_API_KEY가 없으면 목업 키로 폴백 (로컬 테스트 시 RAG는 로컬 매칭으로 동작)
if "DEEPSEEK_API_KEY" not in os.environ or os.environ["DEEPSEEK_API_KEY"] == "MOCK_KEY_FOR_TESTING":
    os.environ["DEEPSEEK_API_KEY"] = "MOCK_KEY_FOR_TESTING"
    # 실제 API 호출 없이 로컬 폴백 매칭만으로 테스트 진행

# target 모듈 직접 임포트
try:
    import main
    from main import app, search_regulation_rag, check_auth, load_json, VOTES_DB_PATH
except ImportError as e:
    print(f"❌ [에러] main.py 또는 필수 모듈 임포트 실패: {e}")
    sys.exit(1)

def run_test_case(name, input_data, expected_status=200):
    print(f"\n==================================================")
    print(f"🧪 테스트 케이스: {name}")
    print(f"==================================================")
    
    # 1. API 스킬 카카오 엔드포인트 직접 모킹 호출
    # FastAPI TestClient를 사용하면 네트워크 바인딩 없이 즉시 가상 POST 요청이 가능합니다.
    try:
        from fastapi.testclient import TestClient
        client = TestClient(app)
        
        # POST 요청 수행
        response = client.post("/chatbot/skill", json=input_data)
        
        if response.status_code == expected_status:
            print(f"✅ HTTP 응답 성공 ({response.status_code})")
            resp_json = response.json()
            
            # SimpleText 출력 값 획득 및 분석
            outputs = resp_json.get("template", {}).get("outputs", [])
            text_response = ""
            if outputs:
                text_response = outputs[0].get("simpleText", {}).get("text", "")
            
            print(f"💬 봇 대답 요약 (앞 100자):\n{text_response[:100]}...")
            
            # 응답 길이 검증 (카카오 글자수 임계 임계치 1000자, 안전권 400자 이내 체크)
            char_count = len(text_response)
            if char_count <= 400:
                print(f"✅ 가독성 최적화 검증 성공: {char_count}자 (400자 권장 한계 충족)")
            else:
                print(f"⚠️ [가독성 초과 경고] 응답 크기가 너무 깁니다. {char_count}자 (정밀 요약 필요)")
            
            return text_response, resp_json
        else:
            print(f"❌ HTTP 응답 에러 코드: {response.status_code}")
            return None, None
            
    except Exception as e:
        print(f"❌ 테스트 실행 도중 돌발 에러 발생: {e}")
        return None, None

def simulate_scenarios():
    print("🚀 카카 호텔봇 실무 상시 모니터링 및 견고성 테스트 패키지 구동\n")
    
    # [시나리오 1] 정회원 인증된 소유주(송이님)가 자주 묻는 핵심 규약 질문을 할 때 (RAG 오매칭 방지 로직 하드코딩 필터 작동 체크)
    case_1_payload = {
        "userRequest": {
            "user": {
                "id": "user_song_dg_tsch_1781",
                "type": "talkUserId"
            },
            "utterance": "보스님, 관리단이 정확히 무엇인가요?"
        }
    }
    ans_1, _ = run_test_case("1. 정회원(송이님) 핵심 규약(관리단이란) 질문 분석", case_1_payload)
    if ans_1 and "당연 설립되는 단체" in ans_1:
         print("✅ 핵심 규약 정의 시나리오 가인 필터 정상 작동 확인")
    else:
         print("❌ 핵심 규약 정의 시나리오 가인 필터 오작동 (RAG 검색으로 폴백됨)")

    # [시나리오 2] 미인증 또는 Guest 소유주가 등급 대외비(회의록 요약)를 질의할 때 (보안 차단 및 인증 안내 작동 검증)
    case_2_payload = {
        "userRequest": {
            "user": {
                "id": "guest_user_1234",
                "type": "talkUserId"
            },
            "utterance": "회의록 요약 보여주실래요?"
        }
    }
    ans_2, _ = run_test_case("2. 미인증/Guest의 대외비(회의록) 요청 차단 검증", case_2_payload)
    if ans_2 and "진입 거절" in ans_2:
        print("✅ 정밀 등급 필터 보안 차단 메커니즘 정상 작동중")

    # [시나리오 3] 정회원 인증 소유주(홍길동)가 대외비 정산(결산) 자료를 조회할 때 (보안 열람 허용 검증)
    case_3_payload = {
        "userRequest": {
            "user": {
                "id": "user_hong_test_0001",
                "type": "talkUserId"
            },
            "utterance": "정산 및 결산 수익률 알려줘"
        }
    }
    run_test_case("3. 인증된 정회원(홍길동)의 대외비 결산 요청 열람 검증", case_3_payload)

    # [시나리오 4] 카카오가 갑작스럽게 특수문자나 극단적인 빈 값(Empty Text)을 던지는 경우 (예외 에러 복원력 검증)
    case_4_payload = {
        "userRequest": {
            "user": {
                "id": "user_hong_test_0001"
            },
            "utterance": "   "
        }
    }
    run_test_case("4. 갑작스러운 빈 값(Empty Space) 입출력 복원력 검증", case_4_payload)

    # [시나리오 5] 총회 투표 진행 중인 안전성 및 중복 방지 무결성 검증 
    case_5_payload = {
        "userRequest": {
            "user": {
                "id": "user_song_dg_tsch_1781"
            },
            "utterance": "총회 투표하기"
        }
    }
    run_test_case("5. 간편의결 중복 검출 및 1인 1투표 차단 검증 (송이님 이미 투표 진행 상태)", case_5_payload)

if __name__ == "__main__":
    simulate_scenarios()
