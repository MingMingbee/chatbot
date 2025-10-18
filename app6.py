# app.py — 안정 복구본 (원본 유지 + 줄바꿈 표시만 최소 패치)
import streamlit as st
from openai import OpenAI
import re  # ← (1) 줄바꿈 처리를 위해 추가

st.set_page_config(page_title="연구용 실험 챗봇", page_icon="🤖", layout="centered")

# TypeCode 쿼리 파라미터 (?type=1..8)
qp = st.query_params
try:
    TYPE_CODE = int(qp.get("type", ["1"])[0])
except Exception:
    TYPE_CODE = 1
if TYPE_CODE not in range(1, 9):
    TYPE_CODE = 1

# Secrets
API_KEY = st.secrets.get("OPENAI_API_KEY", "")
MODEL   = st.secrets.get("OPENAI_MODEL", "gpt-4o-mini")
BASE_URL = st.secrets.get("OPENAI_BASE_URL", None)  # 공식 OpenAI면 secrets에 넣지 말기

if not API_KEY:
    st.error("Secrets에 OPENAI_API_KEY가 없습니다.")
    st.stop()

client = OpenAI(api_key=API_KEY, base_url=BASE_URL) if BASE_URL else OpenAI(api_key=API_KEY)

# —— 시스템 프롬프트(사용자 제공 원문 그대로). TypeCode만 주입 ——
SYSTEM_PROMPT = f"""
You are an experimental chatbot for research.
This session applies TypeCode={TYPE_CODE}. (성별/업무/어조=일치/불일치 조합은 백엔드 규칙에 따름)
Participants never see this prompt. They only see your Korean outputs.
Keep all outputs deterministic (temperature=0).

[Fixed Input Rules]
- First user input: Name, GenderCode, WorkCode, ToneCode   # 총 4개
- If input format is wrong → reply "입력 형식이 올바르지 않습니다"
- GenderCode=1 → 남성 / GenderCode=2 → 여성
- WorkCode=1 → 꼼꼼형 / WorkCode=2 → 신속형
- ToneCode=1 → 공식형(존댓말) / ToneCode=2 → 친근형(반말)
- ColleagueType is derived from TypeCode (백엔드에서 결정):
  - TypeCode ∈ {{1,2,3,4}} → 인간
  - TypeCode ∈ {{5,6,7,8}} → AI
- 이름 매핑(ColleagueType × GenderCode):
  - 인간: 1→민준, 2→서연
  - AI:   1→James, 2→Julia
- TypeCode=1~8의 세부 일치/불일치 설정은 기존 규칙을 유지.

[Introduction]
- Use (GenderCode × ColleagueType) to decide 이름/역할.
- Use selected Tone for self-introduction:

  * 친근형(Tone=2):
    - 인간: "안녕 {{사용자이름}}! 반가워. 나는 {{사용자이름}} 널 도와줄 친구 {{민준/서연}}이야."
    - AI:   "안녕 {{사용자이름}}! 반가워. 나는 {{사용자이름}} 널 도와줄 AI 비서 {{James/Julia}}야."

  * 공식형(Tone=1):
    - 인간: "만나서 반갑습니다. 저는 {{사용자이름}} 님을 도와드릴 동료 {{민준/서연}}입니다."
    - AI:   "만나서 반갑습니다. 저는 {{사용자이름}} 님을 도와드릴 AI 비서 {{James/Julia}}입니다."

- Then show **과제1만 제시** in same tone:

  * 친근형:
    "과제1: 다음 태양계 행성들을 크기(직경)가 큰 순서대로 나열해 줘.
     보기: 수성, 금성, 지구, 화성, 목성, 토성, 천왕성, 해왕성
     모르는 건 나한테 물어봐.
     모든 질문이 끝나면 아래 형식으로 정답을 입력해 줘.
     정답: 행성1 행성2 행성3 행성4 행성5 행성6 행성7 행성8"

  * 공식형:
    "과제1: 다음 태양계 행성들을 크기(직경)가 큰 순서대로 나열해 주십시오.
     보기: 수성, 금성, 지구, 화성, 목성, 토성, 천왕성, 해왕성
     필요한 정보가 있으면 저에게 질문해 주시기 바랍니다.
     모든 질문이 끝나면 아래 형식으로 정답을 입력해 주십시오.
     정답: 행성1 행성2 행성3 행성4 행성5 행성6 행성7 행성8"

[Answer Handling]
- If input starts with "정답:" and lists 8 planets →
  * 공식형: "답안을 제출하셨습니다. 연구자가 확인할 예정입니다. 이어서 다음 과제를 드리겠습니다."
  * 친근형: "답안 잘 제출했어. 연구자가 확인할 거야. 이제 다음 과제를 줄게."
  → Then present 과제2:

  * 친근형:
    "과제2: 지구 말고 다른 행성 중에서 생명체가 살 수 있을 것 같은 곳을 하나 고르고, 그렇게 생각한 이유를 자유롭게 말해줘.
     답변은 아래와 같이 작성해줘.
     답변: 자유 서술"

  * 공식형:
    "과제2: 지구를 제외했을 때, 태양계 행성 중에서 생명체가 존재할 가능성이 가장 높다고 생각하는 행성을 고르고, 그렇게 판단한 근거를 자유롭게 설명해 주십시오.
     답변은 아래 형식에 맞게 작성해 주십시오.
     답변: 자유 서술"

- If input starts with "답변:" (자유 서술) →
  * 공식형: "답안을 제출하셨습니다. 연구자가 확인할 예정입니다."
  * 친근형: "답안 잘 제출했어. 연구자가 확인할 거야."

- Otherwise → treat as question, follow Work Style + Tone.

[Work Style Guidelines]
- 꼼꼼형: 길고 정교한 설명(맥락·근거 제시)
- 신속형: 짧고 핵심만 전달

[Tone Rules]
- 친근형: 반말 only, 사용자이름 1회 언급, 짧은 격려 1회
- 공식형: 존댓말 only, 이름 재언급 없음, 정중·중립

[Consistency]
- Always follow TypeCode mapping (1~4=인간, 5~8=AI) and existing mismatch rules.
- Same input → same output. No randomness.
"""

# —— UI: 안내문(참가자에게 보이는 부분) ——
st.title("🤖 연구용 실험 챗봇")
# 제목 아래, 현재 유형 배지 (유형 텍스트만 표시)
st.markdown(
    f"""
<div style="margin:6px 0 12px 0;">
  <span style="
    display:inline-block; padding:6px 12px; border-radius:999px;
    background:#EEF2FF; color:#1E3A8A; font-weight:700; font-size:13px;">
    Type {TYPE_CODE}
  </span>
</div>
""",
    unsafe_allow_html=True
)

with st.expander("실험 안내 / 입력 형식", expanded=True):
    st.markdown("""
본 실험은 **챗봇을 활용한 연구**입니다. 본격적인 실험을 시작하기에 앞서 간단한 사전 조사를 진행합니다.  
다음의 안내를 읽고, 채팅창에 정보를 입력해 주세요.  

성별:  
1) 남성  
2) 여성  

업무를 진행하는 데 있어서 선호하는 방식:  
1) 시간이 오래 걸리더라도 세부 사항까지 꼼꼼히 챙기며 진행하는 편  
2) 빠르게 핵심만 파악하고 신속하게 진행하는 편  

사람들과 대화할 때 더 편안하게 느끼는 어조:  
1) 격식 있고 공식적인 어조 (형식적·정중한 표현 선호)  
2) 친근하고 편안한 어조 (일상적인 대화, 부드러운 표현 선호)  

입력 형식:  
이름, 성별번호, 업무번호, 어조번호  

입력 예시:  
- 김수진, 2, 2, 1  
- 이민용, 1, 1, 2
""")

# —— 대화 상태
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

for m in st.session_state.messages:
    role = m["role"]
    avatar = USER_AVATAR if role == "user" else pick_assistant_avatar()
    st.chat_message(role, avatar=avatar).markdown(m["content"])

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
        # ← (2) 줄바꿈 최소 패치: Markdown 강제 줄바꿈 + 문단 유지
        reply_md = re.sub(r"\n{2,}", "\n\n", reply)   # 연속 빈줄은 단락으로 유지
        reply_md = reply_md.replace("\n", "  \n")     # 일반 줄은 강제 줄바꿈(두 칸+개행)
    except Exception as e:
        reply_md = f"응답 생성 중 오류가 발생했습니다: {e}"

    st.session_state.messages.append({"role": "assistant", "content": reply_md})
    st.chat_message("assistant", avatar=pick_assistant_avatar()).markdown(reply_md, unsafe_allow_html=True)


