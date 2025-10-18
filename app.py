# app1.py — 최종본 (L8 직교배열: 입력 기반 일치/불일치, Type1용)
import streamlit as st
from openai import OpenAI
import re

st.set_page_config(page_title="연구용 실험 챗봇", page_icon="🤖", layout="centered")

# -----------------------------
# TypeCode 결정: URL ?type=1..8 우선, 없으면 Secrets.BOT_TYPE, 둘 다 없으면 1(app1)
# -----------------------------
qp = st.query_params
def _to_int(x, default):
    try:
        return int(x)
    except:
        return default

TYPE_CODE = _to_int(qp.get("type", [None])[0], _to_int(st.secrets.get("BOT_TYPE", 1), 1))
if TYPE_CODE not in range(1, 9):
    TYPE_CODE = 1  # app1 기본값

# -----------------------------
# Secrets / OpenAI 클라이언트
# -----------------------------
API_KEY  = st.secrets.get("OPENAI_API_KEY", "")
MODEL    = st.secrets.get("OPENAI_MODEL", "gpt-4o-mini")
BASE_URL = st.secrets.get("OPENAI_BASE_URL", None)  # 공식 OpenAI면 비워두기

if not API_KEY:
    st.error("Secrets에 OPENAI_API_KEY가 없습니다.")
    st.stop()

client = OpenAI(api_key=API_KEY, base_url=BASE_URL) if BASE_URL else OpenAI(api_key=API_KEY)

# -----------------------------
# L8 직교배열 매핑표 (성격→어조로 통합)
# Type 1~4: 인간 동료 / Type 5~8: AI 동료
# gender/work/tone: match | mismatch (사용자 입력 기반으로 동적 반전/유지)
# -----------------------------
MATCH_TABLE = {
    1: {'colleague':'human', 'gender':'match',    'work':'match',    'tone':'match'},
    2: {'colleague':'human', 'gender':'match',    'work':'mismatch', 'tone':'mismatch'},
    3: {'colleague':'human', 'gender':'mismatch', 'work':'match',    'tone':'mismatch'},
    4: {'colleague':'human', 'gender':'mismatch', 'work':'mismatch', 'tone':'match'},
    5: {'colleague':'ai',    'gender':'match',    'work':'match',    'tone':'mismatch'},
    6: {'colleague':'ai',    'gender':'match',    'work':'mismatch', 'tone':'match'},
    7: {'colleague':'ai',    'gender':'mismatch', 'work':'match',    'tone':'match'},
    8: {'colleague':'ai',    'gender':'mismatch', 'work':'mismatch', 'tone':'mismatch'},
}
COND = MATCH_TABLE[TYPE_CODE]

# -----------------------------
# UI 헤더
# -----------------------------
st.title("🤖 연구용 실험 챗봇")
st.markdown(
    f"""
<div style="margin:6px 0 12px 0;">
  <span style="display:inline-block;padding:6px 12px;border-radius:999px;background:#EEF2FF;color:#1E3A8A;font-weight:700;font-size:13px;">
    Type {TYPE_CODE} · { '인간동료' if COND['colleague']=='human' else 'AI동료' }
  </span>
</div>
""",
    unsafe_allow_html=True,
)

with st.expander("실험 안내 / 입력 형식", expanded=True):
    st.markdown("""
첫 메시지로 아래 4가지를 쉼표로 구분하여 입력해 주세요.  
형식: `이름, 성별번호, 업무번호, 어조번호`

- 성별번호: 1(남성), 2(여성)  
- 업무번호: 1(꼼꼼형), 2(신속형)    ← 이후 답변 길이/전달 방식에 반영  
- 어조번호: 1(공식형), 2(친근형)  ← 이후 말투에 반영

예시  
- 김수진, 2, 2, 1  
- 이민용, 1, 1, 2
""")

# -----------------------------
# 상태 저장
# -----------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []
if "profile" not in st.session_state:
    st.session_state.profile = None   # {'name','gender','work','tone'}
if "bot_persona" not in st.session_state:
    st.session_state.bot_persona = None  # {'colleague','name','gender','work','tone'}

# -----------------------------
# 유틸 함수
# -----------------------------
def parse_first_input(text: str):
    parts = [p.strip() for p in text.replace("，", ",").split(",")]
    if len(parts) != 4:
        return None
    name = parts[0]
    try:
        g = int(parts[1]); w = int(parts[2]); t = int(parts[3])
    except:
        return None
    if g not in (1,2) or w not in (1,2) or t not in (1,2):
        return None
    return {"name": name, "gender": g, "work": w, "tone": t}

def choose_by_match(user_val: int, match_flag: str):
    if match_flag == "match":
        return user_val
    return 2 if user_val == 1 else 1

def build_bot_persona(profile):
    colleague = COND["colleague"]              # 'human' or 'ai'
    bot_gender = choose_by_match(profile["gender"], COND["gender"])
    bot_work   = choose_by_match(profile["work"],   COND["work"])     # 1=꼼꼼, 2=신속
    bot_tone   = choose_by_match(profile["tone"],   COND["tone"])     # 1=공식, 2=친근

    # 이름 매핑
    if colleague == "human":
        bot_name = "민준" if bot_gender == 1 else "서연"
    else:
        bot_name = "James" if bot_gender == 1 else "Julia"

    return {"colleague": colleague, "name": bot_name, "gender": bot_gender, "work": bot_work, "tone": bot_tone}

def tone_prefix(user_name, colleague, tone):
    # tone: 1=공식, 2=친근
    if tone == 2:
        return f"안녕 {user_name}! 반가워. 나는 너를 도와줄 " + ("친구 " if colleague=="human" else "AI 비서 ")
    else:
        return f"만나서 반갑습니다. 저는 {user_name} 님을 도와드릴 " + ("동료 " if colleague=="human" else "AI 비서 ")

def task1_text(tone):
    if tone == 2:
        return (
            "과제1: 다음 태양계 행성들을 크기(직경)가 큰 순서대로 나열해 줘.\n"
            "보기: 수성, 금성, 지구, 화성, 목성, 토성, 천왕성, 해왕성\n"
            "모르는 건 나한테 물어봐.\n"
            "모든 질문이 끝나면 아래 형식으로 정답을 입력해 줘.\n"
            "정답: 행성1 행성2 행성3 행성4 행성5 행성6 행성7 행성8"
        )
    else:
        return (
            "과제1: 다음 태양계 행성들을 크기(직경)가 큰 순서대로 나열해 주십시오.\n"
            "보기: 수성, 금성, 지구, 화성, 목성, 토성, 천왕성, 해왕성\n"
            "필요한 정보가 있으면 저에게 질문해 주시기 바랍니다.\n"
            "모든 질문이 끝나면 아래 형식으로 정답을 입력해 주십시오.\n"
            "정답: 행성1 행성2 행성3 행성4 행성5 행성6 행성7 행성8"
        )

def task2_text(tone):
    if tone == 2:
        return (
            "과제2: 지구 말고 다른 행성 중에서 생명체가 살 수 있을 것 같은 곳을 하나 고르고, 그렇게 생각한 이유를 자유롭게 말해줘.\n"
            "답변은 아래와 같이 작성해줘.\n"
            "답변: 자유 서술"
        )
    else:
        return (
            "과제2: 지구를 제외했을 때, 태양계 행성 중에서 생명체가 존재할 가능성이 가장 높다고 생각하는 행성을 고르고, 그렇게 판단한 근거를 자유롭게 설명해 주십시오.\n"
            "답변은 아래 형식에 맞게 작성해 주십시오.\n"
            "답변: 자유 서술"
        )

def style_by_work(text, work):
    # work: 1=꼼꼼(길고 맥락 포함), 2=신속(핵심 위주)
    if work == 1:
        return text
    # 신속형: 각 문단을 120자 내로 요약(아주 단순한 컷)
    def _trim_para(p):
        return p if len(p) <= 120 else p[:120] + "…"
    return "\n\n".join(_trim_para(p) for p in text.split("\n\n"))

def render_assistant(md_text):
    md_text = re.sub(r"\n{2,}", "\n\n", md_text)  # 단락 유지
    md_text = md_text.replace("\n", "  \n")       # 일반 줄 강제 줄바꿈
    st.session_state.messages.append({"role":"assistant","content":md_text})
    st.chat_message("assistant", avatar=assistant_avatar()).markdown(md_text, unsafe_allow_html=True)

def assistant_avatar():
    if COND["colleague"] == "ai":
        return "🤖"
    bp = st.session_state.bot_persona
    if not bp:
        return "🧑"
    return "👩" if bp["gender"] == 2 else "🧑"

USER_AVATAR = "🙂"

# 과거 메시지 렌더
for m in st.session_state.messages:
    role = m["role"]
    avatar = USER_AVATAR if role == "user" else assistant_avatar()
    st.chat_message(role, avatar=avatar).markdown(m["content"])

# 입력창
user_text = st.chat_input("메시지를 입력하세요")

if user_text:
    st.session_state.messages.append({"role":"user","content":user_text})
    st.chat_message("user", avatar=USER_AVATAR).markdown(user_text)

    # 1) 첫 입력: 형식 검증 및 봇 페르소나 결정
    if st.session_state.profile is None:
        prof = parse_first_input(user_text)
        if prof is None:
            render_assistant("입력 형식이 올바르지 않습니다")
        else:
            st.session_state.profile = prof
            st.session_state.bot_persona = build_bot_persona(prof)

            bp = st.session_state.bot_persona
            # 인사 + 과제1 제시
            if bp["tone"] == 2:
                intro = f"{tone_prefix(prof['name'], bp['colleague'], 2)}{bp['name']}야."
            else:
                intro = f"{tone_prefix(prof['name'], bp['colleague'], 1)}{bp['name']}입니다."
            msg = intro + "\n\n" + task1_text(bp["tone"])
            render_assistant(style_by_work(msg, bp["work"]))

    # 2) 이후 입력: 자유 처리(형식 검증 없음)
    else:
        bp = st.session_state.bot_persona

        # (a) 과제1 정답 제출
        if user_text.strip().startswith("정답:"):
            msg = (
                "답안을 제출하셨습니다. 연구자가 확인할 예정입니다. 이어서 다음 과제를 드리겠습니다."
                if bp["tone"] == 1 else
                "답안 잘 제출했어. 연구자가 확인할 거야. 이제 다음 과제를 줄게."
            )
            out = msg + "\n\n" + task2_text(bp["tone"])
            render_assistant(style_by_work(out, bp["work"]))
            return

        # (b) 과제2 자유서술
        if user_text.strip().startswith("답변:"):
            msg = (
                "답안을 제출하셨습니다. 연구자가 확인할 예정입니다."
                if bp["tone"] == 1 else
                "답안 잘 제출했어. 연구자가 확인할 거야."
            )
            render_assistant(style_by_work(msg, bp["work"]))
            return

        # (c) 일반 질의응답 → OpenAI 호출 (결정론적)
        sys_prompt = f"""
You are an experimental chatbot for research.
This session applies TypeCode={TYPE_CODE}.
- ColleagueType: {'Human' if COND['colleague']=='human' else 'AI'}
- Output language: Korean only.
- Use the following constraints:
  - tone: {"official" if bp["tone"]==1 else "casual"}
  - work style: {"detailed (context-rich)" if bp["work"]==1 else "concise (essentials-only)"}
- Deterministic outputs (temperature=0). Same input → same output.
- If user asks meta-questions about the task, briefly answer and continue the conversation.
"""
        try:
            with st.spinner("응답 생성 중..."):
                resp = client.chat.completions.create(
                    model=MODEL,
                    messages=[{"role":"system","content":sys_prompt}] + st.session_state.messages,
                    temperature=0,
                    timeout=30,
                )
            reply = resp.choices[0].message.content or ""
            render_assistant(style_by_work(reply, bp["work"]))
        except Exception as e:
            render_assistant(f"응답 생성 중 오류가 발생했습니다: {e}")
