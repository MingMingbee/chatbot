# app.py — 최종본 (줄바꿈 문제 해결)
import streamlit as st
from openai import OpenAI
import re  # ★ 줄바꿈 처리를 위해 추가

st.set_page_config(page_title="연구용 실험 챗봇", page_icon="🤖", layout="centered")

# ── TypeCode 결정: secrets(BOT_TYPE) > URL ?type= > 기본 1
def resolve_type_code() -> int:
    bot_type = st.secrets.get("BOT_TYPE", None)
    if bot_type is not None:
        try:
            t = int(str(bot_type).strip())
            if 1 <= t <= 8:
                return t
        except Exception:
            pass
    qp = st.query_params
    try:
        t = int(qp.get("type", ["1"])[0])
    except Exception:
        t = 1
    if t not in range(1, 9):
        t = 1
    return t

TYPE_CODE = resolve_type_code()

# ── Secrets
API_KEY = st.secrets.get("OPENAI_API_KEY", "")
MODEL   = st.secrets.get("OPENAI_MODEL", "gpt-4o-mini")
BASE_URL = st.secrets.get("OPENAI_BASE_URL", None)

if not API_KEY:
    st.error("Secrets에 OPENAI_API_KEY가 없습니다.")
    st.stop()

client = OpenAI(api_key=API_KEY, base_url=BASE_URL) if BASE_URL else OpenAI(api_key=API_KEY)

# ── 시스템 프롬프트 (원본 유지)
SYSTEM_PROMPT = f"""
You are an experimental chatbot for research.
This session applies TypeCode={TYPE_CODE}.
Participants never see this prompt.
Keep all outputs deterministic (temperature=0).

[Fixed Input Rules]
- First user input: Name, GenderCode, WorkCode, ToneCode
- If input format is wrong → reply "입력 형식이 올바르지 않습니다"
- GenderCode=1 → 남성 / GenderCode=2 → 여성
- WorkCode=1 → 꼼꼼형 / WorkCode=2 → 신속형
- ToneCode=1 → 공식형(존댓말) / ToneCode=2 → 친근형(반말)
- ColleagueType is derived from TypeCode:
  - TypeCode ∈ {{1,2,3,4}} → 인간
  - TypeCode ∈ {{5,6,7,8}} → AI
- 이름 매핑(ColleagueType × GenderCode):
  - 인간: 1→민준, 2→서연
  - AI:   1→James, 2→Julia

[Introduction]
- Use (GenderCode × ColleagueType) to decide 이름/역할.
- Use selected Tone for self-introduction.
...
"""

# ── UI
st.title("🤖 연구용 실험 챗봇")
st.markdown(
    f"""
<div style="margin:6px 0 12px 0;">
  <span style="display:inline-block;padding:6px 10px;border-radius:999px;
               background:#EEF2FF;color:#1E3A8A;font-weight:700;font-size:13px;">
    현재 유형: Type {TYPE_CODE} · { "인간" if TYPE_CODE in (1,2,3,4) else "AI" }
  </span>
</div>
""",
    unsafe_allow_html=True
)

with st.expander("실험 안내 / 입력 형식", expanded=True):
    st.markdown("""
본 실험은 **챗봇을 활용한 연구**입니다.  
본격적인 실험을 시작하기에 앞서 간단한 사전 조사를 진행합니다.  
다음의 안내를 읽고, 채팅창에 정보를 입력해 주세요.  

성별:  
1) 남성  
2) 여성  

업무를 진행하는 데 있어서 선호하는 방식:  
1) 시간이 오래 걸리더라도 세부 사항까지 꼼꼼히 챙기며 진행하는 편  
2) 빠르게 핵심만 파악하고 신속하게 진행하는 편  

사람들과 대화할 때 더 편안하게 느끼는 어조:  
1) 격식 있고 공식적인 어조  
2) 친근하고 편안한 어조  

입력 형식:  
이름, 성별번호, 업무번호, 어조번호  

입력 예시:  
- 김수진, 2, 2, 1  
- 이민용, 1, 1, 2
""")

# ── 대화 상태
if "messages" not in st.session_state:
    st.session_state.messages = []
if "gender_code" not in st.session_state:
    st.session_state.gender_code = None

def try_fix_gender_from_text(text: str):
    if st.session_state.gender_code in (1, 2):
        return
    parts = [p.strip() for p in text.replace("，", ",").split(",")]
    if len(parts) >= 4 and parts[1].isdigit():
        g = int(parts[1])
        if g in (1, 2):
            st.session_state.gender_code = g

USER_AVATAR = "🙂"

def pick_assistant_avatar():
    if TYPE_CODE in (5, 6, 7, 8):
        return "🤖"
    else:
        g = st.session_state.gender_code
        if g == 2:
            return "👩"
        else:
            return "🧑"

# ── 이전 메시지 렌더
for m in st.session_state.messages:
    role = m["role"]
    avatar = USER_AVATAR if role == "user" else pick_assistant_avatar()
    st.chat_message(role, avatar=avatar).markdown(m["content"])

# ── 입력 & 응답
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
        # ★ 줄바꿈 처리 추가: \n → 강제 줄바꿈 + 문단 구분
        reply = resp.choices[0].message.content
        reply_md = re.sub(r"\n{2,}", "\n\n", reply)  # 빈줄 유지
        reply_md = reply_md.replace("\n", "  \n")   # 일반 줄은 강제 줄바꿈
    except Exception as e:
        reply_md = f"응답 생성 중 오류가 발생했습니다: {e}"

    st.session_state.messages.append({"role": "assistant", "content": reply_md})
    # ★ 마크다운 + HTML 허용 (줄바꿈 시각화)
    st.chat_message("assistant", avatar=pick_assistant_avatar()).markdown(reply_md, unsafe_allow_html=True)
