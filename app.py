# app.py — 아바타 4종(인간 남/여, 로봇 남/여) 자동 전환 포함 최소구성
import streamlit as st
from openai import OpenAI

st.set_page_config(page_title="연구용 실험 챗봇", page_icon="🤖", layout="centered")

# ─────────────────────────────
# TypeCode 쿼리 파라미터 (?type=1..8)
# 1~4=인간, 5~8=AI
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
BASE_URL = st.secrets.get("OPENAI_BASE_URL", None)  # 공식 OpenAI면 넣지 않기

# 아바타 이미지 URL(선택). 없으면 이모지 사용
HUMAN_MALE_AVATAR_URL   = st.secrets.get("HUMAN_MALE_AVATAR_URL", "").strip()
HUMAN_FEMALE_AVATAR_URL = st.secrets.get("HUMAN_FEMALE_AVATAR_URL", "").strip()
AI_MALE_AVATAR_URL      = st.secrets.get("AI_MALE_AVATAR_URL", "").strip()
AI_FEMALE_AVATAR_URL    = st.secrets.get("AI_FEMALE_AVATAR_URL", "").strip()

if not API_KEY:
    st.error("Secrets에 OPENAI_API_KEY가 없습니다.")
    st.stop()

client = OpenAI(api_key=API_KEY, base_url=BASE_URL) if BASE_URL else OpenAI(api_key=API_KEY)

# ─────────────────────────────
# 성별코드 추출/고정
#  - 최초 유효 입력(이름, 성별, 업무, 어조)에서 성별코드(1/2) 고정
# ─────────────────────────────
if "gender_code" not in st.session_state:
    st.session_state.gender_code = None  # 1=남, 2=여

def try_fix_gender_from_text(text: str):
    """'이름, 성별번호, 업무번호, 어조번호' 형식에서 성별번호(1/2) 파싱"""
    if st.session_state.gender_code in (1, 2):
        return  # 이미 고정됨
    if not text:
        return
    t = text.replace("，", ",")  # 전각 콤마 대비
    parts = [p.strip() for p in t.split(",")]
    if len(parts) >= 4 and parts[1].isdigit():
        g = int(parts[1])
        if g in (1, 2):
            st.session_state.gender_code = g

def current_gender_code() -> int:
    """알 수 없으면 기본 남성(1)로 표시만 처리"""
    return st.session_state.gender_code if st.session_state.gender_code in (1, 2) else 1

# ─────────────────────────────
# 아바타 결정: 인간/AI × 성별(남/여)
#  - URL이 있으면 URL, 없으면 이모지
# ─────────────────────────────
def pick_assistant_avatar():
    g = current_gender_code()
    if is_ai_colleague(TYPE_CODE):
        if g == 1:
            return AI_MALE_AVATAR_URL if AI_MALE_AVATAR_URL else "🤖"      # 남성형 로봇
        else:
            # 전용 여성 로봇 이미지가 없으면 기본 로봇 이모지 사용
            return AI_FEMALE_AVATAR_URL if AI_FEMALE_AVATAR_URL else "🤖"
    else:
        if g == 1:
            return HUMAN_MALE_AVATAR_URL if HUMAN_MALE_AVATAR_URL else "🧑‍💼"  # 남성 인간
        else:
            return HUMAN_FEMALE_AVATAR_URL if HUMAN_FEMALE_AVATAR_URL else "👩‍💼"  # 여성 인간

USER_AVATAR = "🙂"

# ─────────────────────────────
# 시스템 프롬프트(원문 유지, TypeCode만 주입)
# ─────────────────────────────
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
     답변: 자유 서술"

  * 공식형:
    "과제2: 지구를 제외했을 때, 태양계 행성 중에서 생명체가 존재할 가능성이 가장 높다고 생각하는 행성을 고르고, 그렇게 판단한 근거를 자유롭게 설명해 주십시오.
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

# ─────────────────────────────
# UI: 안내/입력 형식
# ─────────────────────────────
st.title("연구용 실험 챗봇")
with st.expander("실험 안내 / 입력 형식", expanded=True):
    st.markdown("""
본 실험은 **챗봇을 활용한 연구**입니다. 본격적인 실험을 시작하기에 앞서 간단한 사전 조사를 진행합니다.  
다음의 안내를 읽고, 채팅창에 정보를 입력해 주세요.  

성별:  
1) 남성  
2) 여성  

업무 선호:  
1) 시간이 오래 걸려도 꼼꼼하게  
2) 빠르게 핵심만 신속하게  

대화 어조:  
1) 격식 있는 공식형  
2) 친근한 반말형  

입력 형식:  
이름, 성별번호, 업무번호, 어조번호  

입력 예시:  
- 김수진, 2, 2, 1  
- 이민용, 1, 1, 2
""")

# ─────────────────────────────
# 대화 상태
# ─────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []

# 과거 대화 출력 (현재 고정된/추정된 성별 기반 아바타 적용)
for m in st.session_state.messages:
    role = m["role"]
    content = m["content"]
    avatar = USER_AVATAR if role == "user" else pick_assistant_avatar()
    st.chat_message(role, avatar=avatar).markdown(content)

# 입력창
user_text = st.chat_input("메시지를 입력하세요")

if user_text:
    # 최초 입력에서 성별 고정 시도
    try_fix_gender_from_text(user_text)

    # 사용자 메시지 반영/출력
    st.session_state.messages.append({"role": "user", "content": user_text})
    st.chat_message("user", avatar=USER_AVATAR).markdown(user_text)

    # 모델 호출
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

    # 어시스턴트 메시지 저장/표시 (TypeCode × 성별에 맞춰 아바타 자동 적용)
    st.session_state.messages.append({"role": "assistant", "content": reply})
    st.chat_message("assistant", avatar=pick_assistant_avatar()).markdown(reply)
