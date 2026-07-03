# -*- coding: utf-8 -*-
"""
호텔 지식창고 통합 빌더 (v3.0 - Full 2026년 6월 21일 스케일 대응)
역할: "카카" (Kaka)

송이님이 새로 넣어두신 "hotel_shared_chat_summary_full.txt" 실물 텍스트 데이터셋을 
자동 감지하여, 기존 지식창고 책장("hotel_regulation.txt") 전체와 완전 결합 및 RAG 고속 마이닝을 달성합니다.
"""

from pathlib import Path

BASE_DIR = Path("C:/Users/PC/hotel_bot")
KNOWLEDGE_DIR = BASE_DIR / "knowledge"
REG_TXT_PATH = KNOWLEDGE_DIR / "hotel_regulation.txt"
FULL_CHAT_TXT_PATH = KNOWLEDGE_DIR / "hotel_shared_chat_summary_full.txt"

def main():
    print("🚀 [카카 지식 업그레이드]: Full 2026년 6월 21일 연동 스케일 빌드 개시...")

    # 1. 2026년 6월 21일 전역 데이터인 hotel_shared_chat_summary_full.txt 확인
    if not FULL_CHAT_TXT_PATH.exists():
        print(f"오류: {FULL_CHAT_TXT_PATH} 파일을 찾을 수 없습니다. 경로를 확인해 두었습니다.")
        return

    full_chat_content = FULL_CHAT_TXT_PATH.read_text(encoding="utf-8")
    print(f"✅ 2026년 6월 21일용 실세 대화 뼈대 파일 로드 성공 (데이터 크기: {len(full_chat_content)} 자)")

    # 2. hotel_regulation.txt에 해당 데이터를 '최근 최근 대화록 전문 가교' 영역으로 결합
    if REG_TXT_PATH.exists():
        current_reg = REG_TXT_PATH.read_text(encoding="utf-8")
        
        # 중복 병합 방지 보안 필터
        header_marker = "💬 [2026년 6월 21일 최종 통합 텔방 대화록 레코드]"
        if header_marker not in current_reg:
            merged_content = current_reg + f"\n\n{header_marker}\n" + full_chat_content
            REG_TXT_PATH.write_text(merged_content, encoding="utf-8")
            print(f"🥇 대용량 병합 완료! 새로운 최종 교과서 크기: {len(merged_content)} 자")
        else:
            # 주소 내용만 덮어쓰기 또는 갱신 진행
            # 이미 있으면 기존 부분을 제거하거나 새로 덮어 씌우기
            base_part = current_reg.split(header_marker)[0].strip()
            merged_content = base_part + f"\n\n{header_marker}\n" + full_chat_content
            REG_TXT_PATH.write_text(merged_content, encoding="utf-8")
            print(f"🥇 대용량 지식 덮어쓰기 갱신 완료! 최종 교과서 크기: {len(merged_content)} 자")
            
        print("\n🏆 카카 봇 백엔드가 이 대규모 2026년 6월 21일 대화 레코드를 RAG 지식으로 즉시 찾을 수 있게 완전 연동되었습니다!")
    else:
        print("경고: 통합 hotel_regulation.txt 파일이 부재하여 연동을 유예합니다.")

if __name__ == "__main__":
    main()
