# -*- coding: utf-8 -*-
"""
호텔 관리단 카카오 챗봇 백엔드 서버 로컬 테스터 (v2.0)
역할: "카카" (Kaka)
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
        "userRequest": {
            "timezone": "Asia/Seoul",
            "utterance": message,
            "lang": "ko",
            "user": {
                "id": user_id,
                "type": "talkUserId"
            }
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
    print("팩트 기반 정밀 RAG 스킬 테스트")
    # 대리 참석에 관한 진짜 규약 제49조 및 별표8 양식 검증
    run_test("대리 참석 및 위임장 팩트 답변", "user_sung_test_0003", "회의에 대리인 참석 가능한가요?")
