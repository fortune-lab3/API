import os, time, re, base64, io
import streamlit as st
import google.generativeai as genai
from docx import Document

# ==============================
# Gemini 設定
# ==============================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
MODEL_ID = "models/gemini-1.5-flash"

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# ==============================
# CSS / 画像
# ==============================
def load_css(path: str):
    with open(path, "r", encoding="utf-8") as f:
        css = f.read()
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

def load_base64_image(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

logo_light = load_base64_image("img/logo_black.PNG")
logo_dark  = load_base64_image("img/logo_white.PNG")

# ==============================
# セッション
# ==============================
def init_session_state():
    st.session_state.setdefault("current_ad", "")
    st.session_state.setdefault("edited_ad", "")
    st.session_state.setdefault("current_char_count", 0)

# ==============================
# 前後処理
# ==============================
def preprocess(text: str) -> str:
    pattern = re.compile(r'【.*?】|[ＲR][ー-]\d+|■|＊')
    return pattern.sub('', text or "")

def postprocess(text: str) -> str:
    return (text or "").strip().replace("\n", "").replace("\r", "")

def count(text: str) -> int:
    return len((text or "").replace("\n", "").replace("\r", ""))

def realtime_count():
    st.session_state["current_char_count"] = count(
        st.session_state.get("edited_ad", "")
    )

# ==============================
# 保存
# ==============================
def save_docx(text):
    doc = Document()
    doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf

# ==============================
# Gemini 呼び出し
# ==============================
def gemini_chat(prompt, temperature=0.2, max_tokens=512):
    model = genai.GenerativeModel(
        MODEL_ID,
        generation_config={
            "temperature": temperature,
            "max_output_tokens": max_tokens,
        },
    )
    res = model.generate_content(prompt)
    return res.text.strip()

# ==============================
# トーン / キーワード
# ==============================
def split_keywords(keywords: str):
    return [w for w in re.split(r"[ 　]+", keywords.strip()) if w]

def build_keyword(keywords: str):
    words = split_keywords(keywords)
    if not words:
        return ""
    return (
        f"・キーワード指定: { '、'.join(words) }\n"
        "・各キーワードは文章中に1回だけ使用\n"
    )

def build_tone(tone: str) -> str:
    if tone == "やわらかい":
        return (
            "・和語を優先し、ひらがな多め\n"
            "・やさしく親しみのある表現\n"
        )
    return ""

# ==============================
# 文字数調整
# ==============================
def adjust_length(ad, target_length, tone):
    ad = postprocess(ad)
    for _ in range(2):
        diff = target_length - len(ad)
        if abs(diff) <= 5:
            return ad

        cmd = "補って" if diff > 0 else "削って"
        prompt = (
            "次の文章を意味を変えずに文字数だけ調整してください。\n"
            f"{tone}"
            f"現在 {len(ad)} 文字 → {target_length} 文字に{cmd}\n"
            "文章のみ出力\n\n"
            f"【文章】{ad}"
        )
        ad = postprocess(gemini_chat(prompt, temperature=0.1))
    return ad

# ==============================
# 広告生成
# ==============================
def generate_advertisement(text, target_length, keywords, tone):
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY が設定されていません")

    cleaned = preprocess(text)
    tone_txt = build_tone(tone)
    keyword_txt = build_keyword(keywords)

    prompt = (
        "新聞のラテ欄風の広告文を書いてください。\n"
        f"文字数はちょうど {target_length} 文字\n"
        "改行なし、日本語のみ\n"
        "文末に興味を引くフックを入れる\n"
        f"{tone_txt}"
        f"{keyword_txt}\n\n"
        f"【原稿】{cleaned}\n\n【広告文】"
    )

    ad = gemini_chat(prompt, temperature=0.2, max_tokens=int(target_length * 1.5))
    ad = postprocess(ad)
    #ad = adjust_length(ad, target_length, tone_txt)
    return ad

# ==============================
# UI
# ==============================
def main():
    st.set_page_config(page_title="南海ことば工房")
    load_css("style.css")
    init_session_state()

    st.markdown(
        f'<div class="logo-container">'
        f'<img src="data:image/png;base64,{logo_light}" class="logo-light">'
        f'<img src="data:image/png;base64,{logo_dark}" class="logo-dark">'
        f'</div>',
        unsafe_allow_html=True,
    )

    text = st.text_area("広告文にしたい原稿", height=260)

    target_length = st.sidebar.number_input("文字数", 10, 500, 100)
    tone = st.sidebar.radio("文章スタイル", ["かたい", "やわらかい"])
    keywords = st.sidebar.text_input("キーワード（スペース区切り）")

    if st.button("広告文を生成"):
        with st.spinner("生成中..."):
            ad = generate_advertisement(text, target_length, keywords, tone)
            st.session_state["current_ad"] = ad
            st.session_state["edited_ad"] = ad
            st.session_state["current_char_count"] = len(ad)

    if st.session_state["current_ad"]:
        st.text_area("生成結果", key="edited_ad", on_change=realtime_count)
        st.markdown(f"文字数：{st.session_state['current_char_count']}")

        st.download_button(
            "ダウンロード",
            st.session_state["edited_ad"],
            "advertisement.txt",
            "text/plain",
        )

if __name__ == "__main__":
    main()
