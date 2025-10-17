import streamlit as st
from openai import OpenAI
import re

st.set_page_config(page_title="연구용 실험 챗봇", page_icon="🤖", layout="centered")

# ---- URL query: ?type=1..8
qp = st.query_params
try:
    TYPE_CODE = int(qp.get("type", ["1"])[0])
except Exception:
    TYPE_CODE = 1
if TYPE_CODE not in range(1, 9):
    TYPE_CODE = 1

# ---- Secrets (Streamlit Cloud에서 설정)
API_KEY = st.secrets.get("OPENAI_API_KEY", "")
BASE_URL = st.secrets.get("OPENAI_BASE_URL", None)
MODEL   = st.secrets.get("OPENAI_MODEL", "gpt-4o-mini")

if not API_KEY:
    st.info("Settings → Secrets에 OPENAI_API_KEY를 추가하세요.")

client = OpenAI(api_key=API_KEY, base_url=BASE_URL) if BASE_URL else OpenAI(api_key=API_KEY)

# ---- Session state
ss = st.session_state
if "chat" not in ss:
    ss.chat = []
if "profile" not in ss:
    ss.profile = None
if "introduced" not in ss:
    ss.introduced = False

PLANETS = ["수성","금성","지구","화성","목성","토성","천왕성","해왕성"]
HUMAN_NAMES = {1: "민준", 2: "서연"}
AI_NAMES    = {1: "James", 2: "Julia"}
COLLEAGUE_TYPE = "인간" if TYPE_CODE in [1,2,3,4] else "AI"

def make_intro(name, gender_code, tone):
    if COLLEAGUE_TYPE == "인간":
        cname = HUMAN_NAMES.get(gender_code, "민준")
    else:
        cname = AI_NAMES.get(gender_code, "James")
    if tone == 2:  # 친근형
        if COLLEAGUE_TYPE == "인간":
            who = f"안녕 {name}! 반가워. 나는 {name} 널 도와줄 친구 {cname}이야."
        else:
            who = f"안녕 {name}! 반가워. 나는 {name} 널 도와줄 AI 비서 {cname}야."
        task = (
            "과제1: 다음 태양계 행성들을 크기(직경)가 큰 순서대로 나열해 줘.\n"
            "보기: 수성, 금성, 지구, 화성, 목성, 토성, 천왕성, 해왕성\n"
            "모르는 건 나한테 물어봐.\n"
            "모든 질문이 끝나면 아래 형식으로 정답을 입력해 줘.\n"
            "정답: 행성1 행성2 행성3 행성4 행성5 행성6 행성7 행성8"
        )
    else:
        if COLLEAGUE_TYPE == "인간":
            who = f"만나서 반갑습니다. 저는 {name} 님을 도와드릴 동료 {cname}입니다."
        else:
            who = f"만나서 반갑습니다. 저는 {name} 님을 도와드릴 AI 비서 {cname}입니다."
        task = (
            "과제1: 다음 태양계 행성들을 크기(직경)가 큰 순서대로 나열해 주십시오.\n"
            "보기: 수성, 금성, 지구, 화성, 목성, 토성, 천왕성, 해왕성\n"
            "필요한 정보가 있으면 저에게 질문해 주시기 바랍니다.\n"
            "모든 질문이 끝나면 아래 형식으로 정답을 입력해 주십시오.\n"
            "정답: 행성1 행성2 행성3 행성4 행성5 행성6 행성7 행성8"
        )
    return who + "\n\n" + task

def parse_first_input(text: str):
    parts = [p.strip() for p in text.split(',')]
    if len(parts) != 4:
        return None
    name = parts[0]
    nums = []
    for p in parts[1:]:
        m = re.match(r"^(1|2)$", p.strip())
        if not m:
            return None
        nums.append(int(m.group(1)))
    gender, work, tone = nums
    return {"name": name, "gender": gender, "work": work, "tone": tone}

def is_planet_answer(text: str):
    if not text.startswith("정답:"):
        return False
    body = text.replace("정답:", "").strip()
    items = [t.strip() for t in body.split()]
    if len(items) != 8:
        return False
    return all(it in PLANETS for it in items)

def handle_task2_ack(tone: int):
    return "답안을 제출하셨습니다. 연구자가 확인할 예정입니다." if tone == 1 else "답안 잘 제출했어. 연구자가 확인할 거야."

def present_task2(tone: int):
    if tone == 1:
        return ("과제2: 지구를 제외했을 때, 태양계 행성 중에서 생명체가 존재할 가능성이 가장 높다고 생각하는 행성을 고르고, 그렇게 판단한 근거를 자유롭게 설명해 주십시오.\n"
                "답변: 자유 서술")
    else:
        return ("과제2: 지구 말고 다른 행성 중에서 생명체가 살 수 있을 것 같은 곳을 하나 고르고, 그렇게 생각한 이유를 자유롭게 말해줘.\n"
                "답변: 자유 서술")

SYSTEM_PROMPT = open("prompts/system_message.md", "r", encoding="utf-8").read().replace("TypeCode={1..8}", f"TypeCode={TYPE_CODE}")

st.title("🤖 연구용 실험 챗봇")
with st.expander("실험 안내 / 입력 형식", expanded=(ss.profile is None)):
    st.markdown(
        """
본 실험은 **챗봇을 활용한 연구**입니다.  
다음의 안내를 읽고, 채팅창에 정보를 입력해 주세요.  

성별:  
1) 남성  
2) 여성  

업무 선호 방식:  
1) 꼼꼼형  
2) 신속형  

어조 선호:  
1) 공식형  
2) 친근형  

입력 형식:  
`이름, 성별번호, 업무번호, 어조번호`  

입력 예시:  
- 김수진, 2, 2, 1  
- 이민용, 1, 1, 2
        """
    )

chat_box = st.container()
user_text = st.text_area("메시지를 입력하세요", key="input", height=120)
col1, col2 = st.columns([1,1])
with col1:
    send = st.button("보내기", type="primary")
with col2:
    reset = st.button("새로 시작")

if reset:
    ss.chat = []
    ss.profile = None
    ss.introduced = False
    st.experimental_rerun()

with chat_box:
    for msg in ss.chat:
        if msg["role"] == "user":
            st.chat_message("user").markdown(msg["content"])
        else:
            st.chat_message("assistant").markdown(msg["content"])

if send and user_text.strip():
    text = user_text.strip()
    st.session_state.input = ""

    if ss.profile is None:
        parsed = parse_first_input(text)
        if not parsed:
            ss.chat.append({"role":"assistant","content":"입력 형식이 올바르지 않습니다"})
        else:
            ss.profile = parsed
            intro = make_intro(parsed["name"], parsed["gender"], parsed["tone"])
            ss.chat.append({"role":"assistant","content": intro})
            ss.introduced = True
    else:
        profile = ss.profile
        tone = profile["tone"]
        if is_planet_answer(text):
            ack = ("답안을 제출하셨습니다. 연구자가 확인할 예정입니다. 이어서 다음 과제를 드리겠습니다."
                   if tone == 1 else
                   "답안 잘 제출했어. 연구자가 확인할 거야. 이제 다음 과제를 줄게.")
            ss.chat.append({"role":"assistant","content": ack + "\n\n" + present_task2(tone)})
        elif text.startswith("답변:"):
            ss.chat.append({"role":"assistant","content": handle_task2_ack(tone)})
        else:
            work_style = "꼼꼼형: 길고 정교한 설명" if profile["work"] == 1 else "신속형: 짧고 핵심"
            tone_rule  = "친근형: 반말, 이름 1회 언급, 짧은 격려" if tone == 2 else "공식형: 존댓말, 정중·중립"
            sys = SYSTEM_PROMPT + f"\n\n[Runtime Style]\n- {work_style}\n- {tone_rule}\n- TypeCode={TYPE_CODE}, ColleagueType={COLLEAGUE_TYPE}\n"
            msgs = [
                {"role":"system","content": sys},
                {"role":"user","content": text}
            ]
            try:
                resp = client.chat.completions.create(
                    model=MODEL,
                    messages=msgs,
                    temperature=0
                )
                out = resp.choices[0].message.content
            except Exception as e:
                out = f"응답 생성 중 오류가 발생했습니다: {e}"
            ss.chat.append({"role":"user","content": text})
            ss.chat.append({"role":"assistant","content": out})
    st.experimental_rerun()
