# -*- coding: utf-8 -*-
"""
호텔 관리단 카카오 챗봇 백엔드 서버 로컬 테스터 (v1.0)
역할: "카카" (Kaka)

본 테스터는 실제 카카오 챗봇(오픈빌더)이 서버로 보낼 법한
JSON 데이터를 모형화하여 FastAPI 서버에 전송한 뒤,
카카오 규격에 맞는 출력값(JSON)이 보완되어 잘 설계되는지 검토합니다.
"""

import json
from pathlib import Path
import urllib.request
import urllib.parse

API_URL = "http://127.0.0.1:8000/chatbot/skill"

def post_json(url, data_dict):
    encoded = json.dumps(data_dict, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=encoded, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body)
    except Exception as e:
        return 500, {"error": str(e)}


def generate_kakao_payload(user_id, message):
    return {
        "intent": {
            "id": "intent_test_001",
            "name": "일반대화"
        },
        "userRequest": {
            "timezone": "Asia/Seoul",
            "utterance": message,
            "lang": "ko",
            "user": {
                "id": user_id,
                "type": "talkUserId",
                "properties": {}
            }
        },
        "bot": {
            "id": "bot_test_tsch_01",
            "name": "더스테이클래식 봇"
        },
        "action": {
            "name": "스킬_메인",
            "clientExtra": {}
        }
    }


def run_test(scenario_name, user_id, message):
    payload = generate_kakao_payload(user_id, message)
    print(f"\n==========================================")
    print(f"🎬 시나리오: [{scenario_name}]")
    print(f"👤 사용자 ID: {user_id} | 질문: '{message}'")
    print(f"------------------------------------------")
    status, response = post_json(API_URL, payload)
    
    if status == 200:
        outputs = response.get("template", {}).get("outputs", [])
        if outputs:
            text_ans = outputs[0].get("simpleText", {}).get("text", "")
            print(f"🤖 카카 챗봇 (카카오 규격 반환 텍스트):\n{text_ans}")
        else:
            print("응답에 포맷 출력이 비어 있습니다.")
    else:
        print(f"❌ 서버 통신 오류 (HTTP Status: {status})")
        print(response)
    print(f"==========================================")


if __name__ == "__main__":
    print("카카오 챗봇 스킬 연동 가상 시뮬레이션 서버 테스팅을 가동합니다.")
    
    # 1. 미인증 외부인(Guest) 성춘향이 회의록 열람을 요구할 때
    run_test("외부인 정보 차단", "user_sung_test_0003", "지난달 관리단 회의록 열어주세요")
    
    # 2. 임차인 성춘향이 주차 연체 벌금이나 일반 규약 조회를 원할 때 (제90조 2항 및 별표 매칭)
    run_test("일반 자격 규약 RAG 조회", "user_sung_test_0003", "관리비 독촉장 체납자 조치")
    
    # 3. 송이님(인증된 Owner)이 정식 보안인증으로 회의록 조회를 원할 때
    run_test("정식 정회원 회의록 보안 통과", "user_song_dg_tsch_1781", "관리단회의록")
    
    # 4. 송이님이 총회 투표(의결)를 시작하는 기능을 요구할 때
    run_test("총회 간편 찬반 투표 카드 발행", "user_song_dg_tsch_1781", "총회 투표하기")
    
    # 5. 송이님이 총회 투표에서 직접 찬성 의지를 표출할 때
    run_test("의결 투표권 반영 및 보존", "user_song_dg_tsch_1781", "찬성_poll_2026_06_tsch_001")
    
    # 6. 송이님이 이미 투표해놓고 한번 더 중복 투표를 투적하려 할 때
    run_test("의결권 중복 반영 차단 필터", "user_song_dg_tsch_1781", "찬성_poll_2026_06_tsch_001")
