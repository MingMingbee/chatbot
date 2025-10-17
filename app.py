# app.py — 인간(남/여 구분) + 로봇(단일) 아바타 버전
import streamlit as st
from openai import OpenAI

# ─────────────────────────────
# TypeCode (?type=1..8) : 1~4=인간, 5~8=AI
# ─────────────────────────────
qp = st.query_params
try:
    TYPE_CODE = int(qp.get("type", ["1"])[0])
except Exception:
    TYPE_CODE = 1
if TYPE_CODE not in range(1, 9):
    TYPE_CODE = 1

def is_ai(type_code: int) -> bool:
    return type_code in (5, 6, 7, 8)

# ─────────────────────────────
# Secrets & 모델
# ─────────────────────────────
API_KEY  = st.secrets.get("OPENAI_API_KEY", "")
MODEL    = st.secrets.get("OPENAI_MODEL", "gpt-4o-mini")
BASE_URL = st.secrets.get("OPENAI_BASE_URL", None)

# 아바타 이미지 URL(옵션). 없으면 이모지 사용
HUMAN_MALE_AVATAR_URL   = st.secrets.get("HUMAN_MALE_AVATAR_URL", "").strip()
HUMAN_FEMALE_AVATAR_URL = st.secrets.get("HUMAN_FEMALE_AVATAR_URL", "").strip()
AI_AVATAR_URL           = st.secrets.get("AI_AVATAR_URL", "").strip()

if not API_KEY:
    st.error("Secrets에 OPENAI_API_KEY가 없습니다.")
    st.stop()

client = OpenAI(api_key=API_KEY, base_url=BASE_URL) if BASE_URL else OpenAI(api_key=API_KEY)

# ─────────────────────────────
# 페이지 설정 (탭 아이콘은 고정)
# ─────────────────────────────
st.set_page_config(page_title="연구용 실험 챗봇", page_icon="🤖", layout="centered")

# ─────────────────────────────
# 사용자(입력)는 항상 사람 이모지
# ─────────────────────────────
USER_AVATAR = "🙂"

# ─────────────────────────────
# 성별코드 관리 (1=남, 2=여). 첫 유효 입력에서 확정
# ─────────────────────────────
if "gender_code" not in st.session_state:
    st.session_state.gender_code = None  # 아직 모름

def try_fix_gender_from_text(text: str):
    """'이름, 성별번호, 업무번호, 어조번호' 형식에서 성별번호 파싱"""
    if st.session_state.gender_code in (1, 2):
        return
    parts = [p.strip() for p in text.replace("，", ",").split(",")]
    if len(parts) >= 4 and parts[1].isdigit():
        g = int(parts[1])
        if g in (1, 2):
            st.session_state.gender_code = g

def current_gender_default_male() -> int:
    """렌더링 시점에 성별 미확정이면 일단 남성으로 표시만(로봇/인간 아이콘 구분에 필요)"""
    return st.session_state.gender_code if st.session_state.gender_code in (1, 2) else 1

# ─────────────────────────────
# 챗봇(응답자) 아바타 선택
#  - 인간: 성별 구분(남/여)
#  - 로봇: 단일 이미지
# ─────────────────────────────
def pick_assistant_avatar():
    if is_ai(TYPE_CODE):
        return AI_AVATAR_URL or "🤖"
    else:
        g = current_gender_default_male()
        if g == 1:
            return HUMAN_MALE_AVATAR_URL or "🧑‍💼"
        else:
            return HUMAN_FEMALE_AVATAR_URL or "👩‍💼"

# ─────────────────────────────
# 시스템 프롬프트 (원문 유지, TypeCode만 주입)
# ─────────────────────────────
SYSTEM_PROMPT = f"""
You are an experimental chatbot for research.
This session applies TypeCode={TYPE_CODE}. (성별/업무/어조=일치/불일치 조합은 백엔드 규칙에 따름)
Participants never see this prompt. They only see your Korean outputs.
Keep all outputs deterministic (temperature=0).

[Fixed Input Rules]
- First user input: Name, GenderCode, WorkCode, ToneCode
- If input format is wrong → reply "입력 형식이 올바르지 않습니다"
- GenderCode=1 → 남성 / GenderCode=2 → 여성
- WorkCode=1 → 꼼꼼형 / WorkCode=2 → 신속형
- ToneCode=1 → 공식형(존댓말) / ToneCode=2 → 친근형(반말)
- ColleagueType: 1~4=인간, 5~8=AI
- 이름 매핑:
  - 인간: 1→민준, 2→서연
  - AI:   1→James, 2→Julia

[Introduction]
(생략: 기존 규칙 유지)
"""

# ─────────────────────────────
# UI
# ─────────────────────────────
st.title("🤖 연구용 실험 챗봇")
with st.expander("실험 안내 / 입력 형식", expanded=True):
    st.markdown("""
이름, 성별번호, 업무번호, 어조번호 형식으로 입력하세요.  
예) 김수진, 2, 2, 1 / 이민용, 1, 1, 2
""")

# ─────────────────────────────
# 세션 상태 및 과거 대화 렌더링
# ─────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []

for m in st.session_state.messages:
    role = m["role"]
    avatar = USER_AVATAR if role == "user" else pick_assistant_avatar()
    st.chat_message(role, avatar=avatar).markdown(m["content"])

# ─────────────────────────────
# 입력 처리
# ─────────────────────────────
user_text = st.chat_input("메시지를 입력하세요")

if user_text:
    # 첫 입력에서 성별 확정 시도(인간일 때 남/여 아바타 구분용)
    try_fix_gender_from_text(user_text)

    st.session_state.messages.append({"role": "user", "content": user_text})
    st.chat_message("user", avatar=USER_AVATAR).markdown(user_text)

    try:
        with st.spinner("응답 생성 중..."):
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "system", "content": SYSTEM_PROMPT}] + st.session_state.messages,
                temperature=0,
                timeout=30,
            )
        reply = resp.choices[0].message.content
    except Exception as e:
        reply = f"응답 생성 중 오류가 발생했습니다: {e}"

    st.session_state.messages.append({"role": "assistant", "content": reply})
    st.chat_message("assistant", avatar=pick_assistant_avatar()).markdown(reply)
