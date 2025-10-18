# app1.py — Cloud Run 호환(환경변수 우선), 나머지 로직은 기존 그대로
import warnings
warnings.filterwarnings("ignore")
import os
import re
import streamlit as st
from openai import OpenAI

st.set_page_config(page_title="연구용 실험 챗봇", page_icon="🤖", layout="centered")

# ---- Cloud Run에서도 동작하도록: 환경변수 우선 → st.secrets 보조 ----
def get_conf(key, default=None):
    val = os.getenv(key, None)
    if val is not None:
        return val
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default

API_KEY  = get_conf("OPENAI_API_KEY", "")
MODEL    = get_conf("OPENAI_MODEL", "gpt-4o-mini")
BASE_URL = get_conf("OPENAI_BASE_URL", None)

if not API_KEY:
    st.error("OPENAI_API_KEY가 설정되지 않았습니다."); st.stop()

client = OpenAI(api_key=API_KEY, base_url=BASE_URL) if BASE_URL else OpenAI(api_key=API_KEY)

# TypeCode: ?type=1..8 > Secrets.BOT_TYPE > 1
qp = st.query_params
def _to_int(x, default):
    try: return int(x)
    except: return default

TYPE_CODE = _to_int(qp.get("type", [None])[0], _to_int(get_conf("BOT_TYPE", 1), 1))
if TYPE_CODE not in range(1, 9):
    TYPE_CODE = 1

# L8 매핑표(동일)
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

# UI(헤더에 Type만, 1~4 사람 아이콘 유지)
header_icon = "🧑" if COND["colleague"] == "human" else "🤖"
st.title(f"{header_icon} 연구용 실험 챗봇")
st.markdown(f"""
<div style="margin:6px 0 12px 0;">
  <span style="display:inline-block;padding:6px 12px;border-radius:999px;background:#EEF2FF;color:#1E3A8A;font-weight:700;font-size:13px;">
    Type {TYPE_CODE}
  </span>
</div>
""", unsafe_allow_html=True)

# 안내문
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
1) 격식 있고 공식적인 어조  
2) 친근하고 편안한 어조  

입력 형식:  
이름, 성별번호, 업무번호, 어조번호  

입력 예시:  
- 김수진, 2, 2, 1  
- 이민용, 1, 1, 2
""")

# 상태
if "messages" not in st.session_state: st.session_state.messages = []
if "profile"  not in st.session_state: st.session_state.profile  = None
if "bot"      not in st.session_state: st.session_state.bot      = None

# 유틸
def parse_first_input(text: str):
    parts = [p.strip() for p in text.replace("，", ",").split(",")]
    if len(parts) != 4: return None
    name = parts[0]
    try:
        g = int(parts[1]); w = int(parts[2]); t = int(parts[3])
    except: return None
    if g not in (1,2) or w not in (1,2) or t not in (1,2): return None
    return {"name": name, "gender": g, "work": w, "tone": t}

def choose_by_match(user_val: int, flag: str):
    return user_val if flag == "match" else (2 if user_val == 1 else 1)

def build_bot(profile):
    colleague = COND["colleague"]
    b_gender  = choose_by_match(profile["gender"], COND["gender"])
    b_work    = choose_by_match(profile["work"],   COND["work"])
    b_tone    = choose_by_match(profile["tone"],   COND["tone"])
    b_name    = ("민준" if b_gender==1 else "서연") if colleague=="human" else ("James" if b_gender==1 else "Julia")
    return {"colleague": colleague, "name": b_name, "gender": b_gender, "work": b_work, "tone": b_tone}

def intro_line(user_name, bot):
    if bot["tone"] == 2:
        return f"안녕 {user_name}! 반가워. 나는 너를 도와줄 " + ("친구 " if bot["colleague"]=="human" else "AI 비서 ") + f"{bot['name']}야."
    else:
        return f"만나서 반갑습니다. 저는 {user_name} 님을 도와드릴 " + ("동료 " if bot["colleague"]=="human" else "AI 비서 ") + f"{bot['name']}입니다."

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
    return text  # 신속형이라도 자르지 않음

def render_assistant(md_text):
    md_text = re.sub(r"\n{2,}", "\n\n", md_text.strip())
    st.session_state.messages.append({"role":"assistant","content":md_text})
    st.chat_message("assistant", avatar=assistant_avatar()).write(md_text)

def assistant_avatar():
    if COND["colleague"] == "ai": return "🤖"
    b = st.session_state.bot
    return "👩" if (b and b["gender"]==2) else "🧑"

USER_AVATAR = "🙂"

# 과거 메시지 표시
for m in st.session_state.messages:
    role = m["role"]
    st.chat_message(role, avatar=(USER_AVATAR if role=="user" else assistant_avatar())).write(m["content"])

# 입력
user_text = st.chat_input("메시지를 입력하세요")

if user_text:
    st.session_state.messages.append({"role":"user","content":user_text})
    st.chat_message("user", avatar=USER_AVATAR).write(user_text)

    if st.session_state.profile is None:
        prof = parse_first_input(user_text)
        if prof is None:
            render_assistant("입력 형식이 올바르지 않습니다")
        else:
            st.session_state.profile = prof
            st.session_state.bot = build_bot(prof)
            bot = st.session_state.bot
            first = intro_line(prof["name"], bot) + "\n\n" + task1_text(bot["tone"])
            render_assistant(style_by_work(first, bot["work"]))
    else:
        bot = st.session_state.bot
        txt = user_text.strip()

        if txt.startswith("정답:"):
            confirm = ("답안을 제출하셨습니다. 연구자가 확인할 예정입니다. 이어서 다음 과제를 드리겠습니다."
                       if bot["tone"]==1 else
                       "답안 잘 제출했어. 연구자가 확인할 거야. 이제 다음 과제를 줄게.")
            render_assistant(style_by_work(confirm + "\n\n" + task2_text(bot["tone"]), bot["work"]))

        elif txt.startswith("답변:"):
            confirm = ("답안을 제출하셨습니다. 연구자가 확인할 예정입니다."
                       if bot["tone"]==1 else
                       "답안 잘 제출했어. 연구자가 확인할 거야.")
            render_assistant(style_by_work(confirm, bot["work"]))

        else:
            sys_prompt = f"""
You are an experimental chatbot for research.
This session applies TypeCode={TYPE_CODE}.
- ColleagueType: {'Human' if COND['colleague']=='human' else 'AI'}
- Output language: Korean only.
- Constraints:
  - tone: {"official" if bot["tone"]==1 else "casual"}
  - work style: {"detailed (context-rich)" if bot["work"]==1 else "concise (essentials-only)"}
- Deterministic outputs (temperature=0). Same input → same output.
"""
            try:
                with st.spinner("응답 생성 중..."):
                    resp = client.chat.completions.create(
                        model=MODEL,
                        messages=[{"role":"system","content":sys_prompt}] + st.session_state.messages,
                        temperature=0,
                    )
                reply = resp.choices[0].message.content or ""
                render_assistant(style_by_work(reply, bot["work"]))
            except Exception as e:
                render_assistant(f"응답 생성 중 오류가 발생했습니다: {e}")

