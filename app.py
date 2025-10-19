# app1.py — 과제2 종료 처리(입력창 숨김 + 종료 안내 + 재시작)
import warnings
warnings.filterwarnings("ignore")

import logging, os, re
logging.getLogger("streamlit.runtime.secrets").setLevel(logging.ERROR)

import streamlit as st
from openai import OpenAI

st.set_page_config(page_title="연구용 실험 챗봇", page_icon="🤖", layout="centered")

# -----------------------------
# 설정 로드: ENV 우선 → secrets 보조
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
def _to_int(x, default):
    try: return int(x)
    except: return default
TYPE_CODE = _to_int(qp.get("type"), _to_int(get_conf("BOT_TYPE", 1), 1))
TYPE_CODE = TYPE_CODE if TYPE_CODE in range(1,9) else 1

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
header_icon = "🧑" if COND["colleague"] == "human" else "🤖"
st.title(f"{header_icon} 연구용 실험 챗봇")
st.markdown(f"""
<div style="margin:6px 0 12px 0;">
  <span style="display:inline-block;padding:6px 12px;border-radius:999px;background:#EEF2FF;color:#1E3A8A;font-weight:700;font-size:13px;">
    Type {TYPE_CODE}
  </span>
</div>
""", unsafe_allow_html=True)

# ✅ 안내 블록(사용자 요청 문구 그대로)
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
""")

# -----------------------------
# 상태
# -----------------------------
ss = st.session_state
if "messages" not in ss: ss.messages = []
if "profile"  not in ss: ss.profile  = None
if "bot"      not in ss: ss.bot      = None
if "stage"    not in ss: ss.stage    = 0  # 0:사전입력, 1:과제1, 2:과제2, 3:종료

def reset_all():
    for k in ("messages","profile","bot","stage","_prefill"):
        if k in ss: del ss[k]
    st.rerun()

USER_AVATAR = "🙂"

def assistant_avatar():
    if COND["colleague"] == "ai": return "🤖"
    b = ss.bot
    return "👩" if (b and b["gender"]==2) else "🧑"

def render_assistant(text):
    import re as _re
    text = _re.sub(r"\n{2,}", "\n\n", text.strip())
    ss.messages.append({"role":"assistant","content":text})
    st.chat_message("assistant", avatar=assistant_avatar()).write(text)

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
    return (f"안녕 {user_name}! 반가워. 나는 너를 도와줄 "
            + ("친구 " if bot["colleague"]=="human" else "AI 비서 ") + f"{bot['name']}야."
            ) if bot["tone"]==2 else (
            f"만나서 반갑습니다. 저는 {user_name} 님을 도와드릴 "
            + ("동료 " if bot["colleague"]=="human" else "AI 비서 ") + f"{bot['name']}입니다."
            )

def task1_text(tone):
    return (
        "과제1: 다음 태양계 행성들을 **직경이 큰 순서**로 나열해 주세요.\n"
        "보기: 수성, 금성, 지구, 화성, 목성, 토성, 천왕성, 해왕성\n"
        "제출 형식: `정답: 행성1, 행성2, …, 행성8`"
    ) if tone==1 else (
        "과제1: 보기의 행성을 **직경 큰 순서**로 나열해 줘.\n"
        "보기: 수성, 금성, 지구, 화성, 목성, 토성, 천왕성, 해왕성\n"
        "제출 형식: `정답: 행성1, 행성2, …, 행성8`"
    )

def task2_text(tone):
    return (
        "과제2: 지구를 제외하고 **생명체 존재 가능성이 높다**고 보는 행성 1개와 근거를 작성해 주십시오.\n"
        "제출 형식: `답변: 자유 서술`"
    ) if tone==1 else (
        "과제2: 지구 말고 **생명체가 살 수 있을 것 같은** 행성 1개를 고르고, 이유를 써줘.\n"
        "제출 형식: `답변: 자유 서술`"
    )

def style_by_work(text, work):  # 신속형도 내용은 유지
    return text

PLANETS = ["수성","금성","지구","화성","목성","토성","천왕성","해왕성"]
def is_planet_sequence_answer(s: str) -> bool:
    s = s.strip()
    s = re.sub(r"^(정답)\s*[:\-]?\s*", "", s, flags=re.IGNORECASE)
    parts = [p.strip() for p in s.split(",")]
    if len(parts) != 8: return False
    if len(set(parts)) != 8: return False
    return all(p in PLANETS for p in parts)

# -----------------------------
# 진행 보조/재시작 UI
# -----------------------------
top_cols = st.columns([1,1,1])
with top_cols[0]:
    if ss.stage == 0 and st.button("사전입력 예시 붙여넣기"):
        ss["_prefill"] = "이민용, 1, 1, 2"
with top_cols[1]:
    if ss.stage == 1 and st.button("다음 과제로 넘어가기"):
        ss.stage = 2
        render_assistant(style_by_work(task2_text(ss.bot["tone"]), ss.bot["work"]))
with top_cols[2]:
    if st.button("재시작"):
        reset_all()

# -----------------------------
# 종료 상태면 안내 띄우고 입력창 숨김
# -----------------------------
if ss.stage == 3:
    st.success("실험이 종료되었습니다. 참여해 주셔서 감사합니다.")
    st.caption("이 창을 닫으셔도 되고, 위의 ‘재시작’ 버튼으로 처음부터 다시 참여할 수 있습니다.")
    st.stop()

# -----------------------------
# 입력창(종료 상태가 아니어야 노출)
# -----------------------------
default_prompt = ss.pop("_prefill", None)
user_text = st.chat_input("메시지를 입력하세요", value=default_prompt if default_prompt else "")

# -----------------------------
# 대화 흐름(단계 기반)
# -----------------------------
if user_text:
    ss.messages.append({"role":"user","content":user_text})
    st.chat_message("user", avatar=USER_AVATAR).write(user_text)

    # 0) 사전입력
    if ss.stage == 0:
        prof = parse_first_input(user_text)
        if prof is None:
            render_assistant("입력 형식이 올바르지 않습니다.\n예) 김수진, 2, 2, 1  /  이민용, 1, 1, 2")
        else:
            ss.profile = prof
            ss.bot     = build_bot(prof)
            ss.stage   = 1
            first = intro_line(prof["name"], ss.bot) + "\n\n" + task1_text(ss.bot["tone"])
            render_assistant(style_by_work(first, ss.bot["work"]))

    # 1) 과제1
    elif ss.stage == 1:
        txt = user_text.strip()
        if txt.startswith(("정답", "정답:", "정답 -")) or is_planet_sequence_answer(txt):
            tip = ""
            if not is_planet_sequence_answer(txt):
                tip = ("\n\n(참고: 보기의 8개 행성을 **중복 없이** 모두 포함해 주세요.)"
                       if ss.bot["tone"]==1 else
                       "\n\n(참고: 보기 8개 행성을 **중복 없이** 다 적어줘!)")
            confirm = ("답안이 접수되었습니다. 이어서 과제2를 진행하겠습니다."
                       if ss.bot["tone"]==1 else
                       "답안 확인했어! 이제 과제2로 넘어가자.")
            ss.stage = 2
            render_assistant(style_by_work(confirm + tip + "\n\n" + task2_text(ss.bot["tone"]), ss.bot["work"]))
        else:
            # 힌트/질문 응답
            sys_prompt = f"""
You are an experimental chatbot for research.
Session TypeCode={TYPE_CODE}. (사용자 노출 금지)
Output: Korean only. Deterministic (temperature=0).
- ColleagueType: {"Human" if COND['colleague']=="human" else "AI"}
- Tone: {"official/polite" if ss.bot["tone"]==1 else "casual/friendly"}
- Work style: {"detailed (context-rich)" if ss.bot["work"]==1 else "concise (essentials-only)"}
Rules:
1) 과제 완수를 돕는 범위에서 명확하게 답하라.
2) 제출 형식(정답:/답변:)을 가볍게 상기시켜라.
3) 불확실하면 '확인 필요'라고 말하라.
4) 동일 입력 → 동일 출력.
"""
            try:
                with st.spinner("응답 생성 중..."):
                    resp = client.chat.completions.create(
                        model=MODEL,
                        messages=[{"role":"system","content":sys_prompt}] + ss.messages,
                        temperature=0,
                    )
                reply = resp.choices[0].message.content or ""
                render_assistant(style_by_work(reply, ss.bot["work"]))
            except Exception as e:
                render_assistant(f"응답 생성 중 오류가 발생했습니다: {e}")

    # 2) 과제2
    elif ss.stage == 2:
        txt = user_text.strip()
        if txt.startswith("답변"):
            closing = ("답변을 제출하셨습니다. 참여해 주셔서 감사합니다. 본 실험은 여기까지이며, 입력은 더 이상 받지 않습니다."
                       if ss.bot["tone"]==1 else
                       "답변 잘 받았어! 참여 고마워. 실험은 여기까지야, 이제 입력은 받지 않아.")
            render_assistant(style_by_work(closing, ss.bot["work"]))
            ss.stage = 3  # ✅ 종료 전환
            st.rerun()    # 입력창 숨김을 즉시 반영
        else:
            # 자유 질의응답(과제2 보조)
            sys_prompt = f"""
You are an experimental chatbot for research.
Session TypeCode={TYPE_CODE}. (사용자 노출 금지)
Output: Korean only. Deterministic (temperature=0).
- ColleagueType: {"Human" if COND['colleague']=="human" else "AI"}
- Tone: {"official/polite" if ss.bot["tone"]==1 else "casual/friendly"}
- Work style: {"detailed (context-rich)" if ss.bot["work"]==1 else "concise (essentials-only)"}
Task:
- 참가자가 과제2 답변을 마무리할 수 있게 질문/정리를 돕고,
- 제출 형식 `답변:`을 부드럽게 상기시켜라.
"""
            try:
                with st.spinner("응답 생성 중..."):
                    resp = client.chat.completions.create(
                        model=MODEL,
                        messages=[{"role":"system","content":sys_prompt}] + ss.messages,
                        temperature=0,
                    )
                reply = resp.choices[0].message.content or ""
                render_assistant(style_by_work(reply, ss.bot["work"]))
            except Exception as e:
                render_assistant(f"응답 생성 중 오류가 발생했습니다: {e}")
