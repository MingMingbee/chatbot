# app.py — 원래 코드 유지 + 챗봇 아바타(인간 남/여, 로봇 단일) + 남자 이모지 교체(🧑)
import streamlit as st
from openai import OpenAI

st.set_page_config(page_title="연구용 실험 챗봇", page_icon="🤖", layout="centered")

# ─────────────────────────────
# TypeCode (?type=1..8): 1~4=인간, 5~8=AI
# ─────────────────────────────
qp = st.query_params
try:
    TYPE_CODE = int(qp.get("type", ["1"])[0])
except Exception:
    TYPE_CODE = 1
if TYPE_CODE not in range(1, 9):
    TYPE_CODE = 1

def is_ai_colleague(type_code: int) -> bool:
    return type_code in (5, 6, 7, 8)

# ─────────────────────────────
# Secrets
# ─────────────────────────────
API_KEY  = st.secrets.get("OPENAI_API_KEY", "")
MODEL    = st.secrets.get("OPENAI_MODEL", "gpt-4o-mini")
BASE_URL = st.secrets.get("OPENAI_BASE_URL", None)

HUMAN_MALE_AVATAR_URL   = st.secrets.get("HUMAN_MALE_AVATAR_URL", "").strip()
HUMAN_FEMALE_AVATAR_URL = st.secrets.get("HUMAN_FEMALE_AVATAR_URL", "").strip()
AI_AVATAR_URL           = st.secrets.get("AI_AVATAR_URL", "").strip()

if not API_KEY:
    st.error("Secrets에 OPENAI_API_KEY가 없습니다.")
    st.stop()

client = OpenAI(api_key=API_KEY, base_url=BASE_URL) if BASE_URL else OpenAI(api_key=API_KEY)

# ─────────────────────────────
# 시스템 프롬프트 (원문 유지)
# ─────────────────────────────
SYSTEM_PROMPT = f"""
You are an experimental chatbot for research.
This session applies TypeCode={TYPE_CODE}.
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
"""

# ─────────────────────────────
# UI 안내
# ─────────────────────────────
st.title("🤖 연구용 실험 챗봇")
with st.expander("실험 안내 / 입력 형식", expanded=True):
    st.markdown("""
본 실험은 **챗봇을 활용한 연구**입니다.  
이름, 성별번호, 업무번호, 어조번호 형식으로 입력하세요.  
예: 김수진, 2, 2, 1
""")

# ─────────────────────────────
# 세션 초기화
# ─────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []
if "gender_code" not in st.session_state:
    st.session_state.gender_code = None

# 성별코드 추출
def try_fix_gender_from_text(text: str):
    if st.session_state.gender_code in (1, 2):
        return
    parts = [p.strip() for p in text.replace("，", ",").split(",")]
    if len(parts) >= 4 and parts[1].isdigit():
        g = int(parts[1])
        if g in (1, 2):
            st.session_state.gender_code = g

# 사용자 아바타: 고정
USER_AVATAR = "🙂"

# 챗봇 아바타 선택 함수
def pick_assistant_avatar() -> str:
    if is_ai_colleague(TYPE_CODE):
        return AI_AVATAR_URL if AI_AVATAR_URL else "🤖"
    else:
        g = st.session_state.gender_code
        if g == 2:
            return HUMAN_FEMALE_AVATAR_URL if HUMAN_FEMALE_AVATAR_URL else "👩"
        elif g == 1:
            return HUMAN_MALE_AVATAR_URL if HUMAN_MALE_AVATAR_URL else "🧑"
        else:
            return "🧑"  # 성별 미확정 시 기본 사람 얼굴

# ─────────────────────────────
# 과거 대화 출력
# ─────────────────────────────
for m in st.session_state.messages:
    role = m["role"]
    avatar = USER_AVATAR if role == "user" else pick_assistant_avatar()
    st.chat_message(role, avatar=avatar).markdown(m["content"])

# ─────────────────────────────
# 입력 처리
# ─────────────────────────────
user_text = st.chat_input("메시지를 입력하세요")

if user_text:
    st.session_state.messages.append({"role": "user", "content": user_text})
    st.chat_message("user", avatar=USER_AVATAR).markdown(user_text)
    try_fix_gender_from_text(user_text)

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
