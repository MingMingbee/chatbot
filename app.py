# app1.py — 사전입력 예시 제거 + placeholder 적용 + 종료 처리 유지
import warnings
warnings.filterwarnings("ignore")

import logging, os, re
logging.getLogger("streamlit.runtime.secrets").setLevel(logging.ERROR)

import streamlit as st
from openai import OpenAI

st.set_page_config(page_title="연구용 실험 챗봇", page_icon="🤖", layout="centered")

# -----------------------------
# 설정(ENV 우선 → secrets 보조)
# -----------------------------
def get_conf(key, default=None):
    val = os.getenv(key)
    if val not in (None, ""):
        return val
    paths = ("/app/.streamlit/secrets.toml", "/root/.streamlit/secrets.toml")
    if any(os.path.exists(p) for p in paths):
        try:
            return st.secrets.get(key, default)
        except Exception:
            pass
    return default

API_KEY  = get_conf("OPENAI_API_KEY", "")
MODEL    = get_conf("OPENAI_MODEL", "gpt-4o-mini")
BASE_URL = get_conf("OPENAI_BASE_URL", None)
if not API_KEY:
    st.error("OPENAI_API_KEY가 설정되지 않았습니다."); st.stop()
client = OpenAI(api_key=API_KEY, base_url=BASE_URL) if BASE_URL else OpenAI(api_key=API_KEY)

# -----------------------------
# TypeCode
# -----------------------------
qp = st.query_params
def _to_int(x, d): 
    try: return int(x)
    except: return d

TYPE_CODE = _to_int(qp.get("type"), _to_int(get_conf("BOT_TYPE", 1), 1))
TYPE_CODE = TYPE_CODE if TYPE_CODE in range(1,9) else 1

MATCH_TABLE = {
    1:{'colleague':'human','gender':'match','work':'match','tone':'match'},
    2:{'colleague':'human','gender':'match','work':'mismatch','tone':'mismatch'},
    3:{'colleague':'human','gender':'mismatch','work':'match','tone':'mismatch'},
    4:{'colleague':'human','gender':'mismatch','work':'mismatch','tone':'match'},
    5:{'colleague':'ai','gender':'match','work':'match','tone':'mismatch'},
    6:{'colleague':'ai','gender':'match','work':'mismatch','tone':'match'},
    7:{'colleague':'ai','gender':'mismatch','work':'match','tone':'match'},
    8:{'colleague':'ai','gender':'mismatch','work':'mismatch','tone':'mismatch'},
}
COND = MATCH_TABLE[TYPE_CODE]

# -----------------------------
# UI 헤더
# -----------------------------
header_icon = "🧑" if COND["colleague"]=="human" else "🤖"
st.title(f"{header_icon} 연구용 실험 챗봇")
st.markdown(f"""
<div style="margin:6px 0 12px 0;">
  <span style="display:inline-block;padding:6px 12px;border-radius:999px;background:#EEF2FF;color:#1E3A8A;font-weight:700;font-size:13px;">
    Type {TYPE_CODE}
  </span>
</div>
""", unsafe_allow_html=True)

# ✅ 안내 블록
with st.expander("실험 안내 / 입력 형식", expanded=True):
    st.markdown("""
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

**제출 규칙(중요):**  
- 챗봇과의 질문이 끝난 후 **과제1 정답을 제출할 때는 반드시 앞에 `정답:`을 쓰고** 답을 입력해 주세요.  
  예) `정답: 행성1, 행성2, …, 행성8`  
- **과제2(주관식)도 반드시 앞에 `답변:`을 쓰고** 입력해 주세요.  
  예) `답변: 자유 서술`
""")

# -----------------------------
# 상태
# -----------------------------
ss = st.session_state
if "messages" not in ss: ss.messages = []
if "profile"  not in ss: ss.profile  = None
if "bot"      not in ss: ss.bot      = None
if "stage"    not in ss: ss.stage    = 0  # 0:사전입력, 1:과제1, 2:과제2, 3:종료

USER_AVATAR = "🙂"

def reset_all():
    for k in ("messages","profile","bot","stage"):
        if k in ss: del ss[k]
    st.rerun()

def assistant_avatar():
    if COND["colleague"]=="ai": return "🤖"
    b = ss.bot
    return "👩" if (b and b["gender"]==2) else "🧑"

def render_assistant(t):
    t = re.sub(r"\n{2,}", "\n\n", t.strip())
    ss.messages.append({"role":"assistant","content":t})
    st.chat_message("assistant", avatar=assistant_avatar()).write(t)

# 과거 메시지
for m in ss.messages:
    st.chat_message(m["role"], avatar=(USER_AVATAR if m["role"]=="user" else assistant_avatar())).write(m["content"])

# -----------------------------
# 유틸
# -----------------------------
def parse_first_input(text: str):
    parts = [p.strip() for p in text.replace("，", ",").split(",")]
    if len(parts) != 4: return None
    name = parts[0]
    try:
        g = int(parts[1]); w = int(parts[2]); t = int(parts[3])
    except: return None
    if g not in (1,2) or w not in (1,2) or t not in (1,2): return None
    return {"name": name, "gender": g, "work": w, "tone": t}

def choose_by_match(v, flag): 
    return v if flag=="match" else (2 if v==1 else 1)

def build_bot(profile):
    c = COND["colleague"]
    bg = choose_by_match(profile["gender"], COND["gender"])
    bw = choose_by_match(profile["work"], COND["work"])
    bt = choose_by_match(profile["tone"], COND["tone"])
    bname = ("민준" if bg==1 else "서연") if c=="human" else ("James" if bg==1 else "Julia")
    return {"colleague": c, "name": bname, "gender": bg, "work": bw, "tone": bt}

def intro_line(name, bot):
    return (f"안녕 {name}! 반가워. 나는 너를 도와줄 " + ("친구 " if bot["colleague"]=="human" else "AI 비서 ") + f"{bot['name']}야."
            if bot["tone"]==2 else
            f"만나서 반갑습니다. 저는 {name} 님을 도와드릴 " + ("동료 " if bot["colleague"]=="human" else "AI 비서 ") + f"{bot['name']}입니다.")

def task1_text(tone):
    return (
        "과제1: 보기의 행성을 **직경 큰 순서**로 나열해 주세요.\n"
        "보기: 수성, 금성, 지구, 화성, 목성, 토성, 천왕성, 해왕성\n"
        "모든 질문을 마친 뒤 **정답을 제출할 때는 반드시 앞에 `정답:`을 쓰고** 입력해 주세요.\n"
        "예) `정답: 행성1, 행성2, …, 행성8`"
    ) if tone==1 else (
        "과제1: 보기의 행성을 **직경 큰 순서**로 나열해 줘.\n"
        "보기: 수성, 금성, 지구, 화성, 목성, 토성, 천왕성, 해왕성\n"
        "모든 질문을 마친 뒤 **정답을 제출할 때는 앞에 `정답:`을 꼭 써줘.**\n"
        "예) `정답: 행성1, 행성2, …, 행성8`"
    )

def task2_text(tone):
    return (
        "과제2: 지구를 제외하고 **생명체 존재 가능성이 높다**고 보는 행성 1개와 근거를 작성해 주세요.\n"
        "제출 시 **반드시 앞에 `답변:`을 쓰고** 입력해 주세요.\n"
        "예) `답변: 자유 서술`"
    ) if tone==1 else (
        "과제2: 지구 말고 **생명체가 살 수 있을 것 같은** 행성 1개를 골라 이유를 써줘.\n"
        "제출할 때는 **앞에 `답변:`을 꼭 붙여줘.**\n"
        "예) `답변: 자유 서술`"
    )

def style_by_work(text, work): return text
PLANETS = ["수성","금성","지구","화성","목성","토성","천왕성","해왕성"]
def is_planet_sequence_answer(s: str):
    s = re.sub(r"^(정답)\s*[:\-]?\s*", "", s.strip(), flags=re.IGNORECASE)
    parts = [p.strip() for p in s.split(",")]
    return len(parts)==8 and len(set(parts))==8 and all(p in PLANETS for p in parts)

# -----------------------------
# 보조 버튼
# -----------------------------
cols = st.columns([1,1])
with cols[0]:
    if ss.stage==1 and st.button("다음 과제로 넘어가기"):
        ss.stage = 2
        render_assistant(style_by_work(task2_text(ss.bot["tone"]), ss.bot["work"]))
with cols[1]:
    if st.button("재시작"):
        reset_all()

# -----------------------------
# 종료 처리
# -----------------------------
if ss.stage==3:
    st.success("실험이 종료되었습니다. 참여해 주셔서 감사합니다.")
    st.caption("창을 닫으셔도 되고, ‘재시작’ 버튼으로 처음부터 다시 참여할 수 있습니다.")
    st.stop()

# -----------------------------
# 입력창 (placeholder만 사용)
# -----------------------------
placeholder = (
    "예) 이름, 성별번호, 업무번호, 어조번호 → 이민용, 1, 1, 2" if ss.stage==0 else
    ("예) 정답: 목성, 토성, 천왕성, 해왕성, 지구, 금성, 화성, 수성" if ss.stage==1 else
     "예) 답변: 자유 서술")
)
user_text = st.chat_input("메시지를 입력하세요", placeholder=placeholder)

# -----------------------------
# 대화 흐름
# -----------------------------
if user_text:
    ss.messages.append({"role":"user","content":user_text})
    st.chat_message("user", avatar=USER_AVATAR).write(user_text)

    if ss.stage==0:
        prof = parse_first_input(user_text)
        if prof is None:
            render_assistant("입력 형식이 올바르지 않습니다.\n예) 김수진, 2, 2, 1  /  이민용, 1, 1, 2")
        else:
            ss.profile = prof
            ss.bot     = build_bot(prof)
            ss.stage   = 1
            render_assistant(style_by_work(intro_line(prof["name"], ss.bot) + "\n\n" + task1_text(ss.bot["tone"]), ss.bot["work"]))

    elif ss.stage==1:
        txt = user_text.strip()
        if txt.startswith(("정답", "정답:", "정답 -")) or is_planet_sequence_answer(txt):
            ss.stage = 2
            render_assistant(style_by_work("정답을 확인했습니다. 이제 두 번째 과제로 넘어가겠습니다.\n\n" + task2_text(ss.bot["tone"]), ss.bot["work"]))
        else:
            render_assistant(style_by_work("정답을 제출할 때는 반드시 `정답:`을 붙여주세요.", ss.bot["work"]))

    elif ss.stage==2:
        txt = user_text.strip()
        if txt.startswith("답변"):
            render_assistant(style_by_work("답변을 잘 받았습니다. 참여해 주셔서 감사합니다. 실험은 여기서 종료됩니다.", ss.bot["work"]))
            ss.stage = 3
            st.rerun()
        else:
            render_assistant(style_by_work("답변을 제출할 때는 반드시 `답변:`을 붙여주세요.", ss.bot["work"]))
