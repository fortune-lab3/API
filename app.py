import os, time, re, base64, io
import streamlit as st
from huggingface_hub import InferenceClient
from httpx import ConnectTimeout, ReadTimeout, HTTPError
from docx import Document

# Hugging Face 設定
HF_TOKEN = os.getenv("HUGGINGFACEHUB_API_TOKEN", "")
MODEL_ID = "Qwen/Qwen3-4B-Instruct-2507"

# CSS
def load_css(path: str):
    with open(path, "r", encoding="utf-8") as f:
        css = f.read()
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

def load_base64_image(path):
    with open(path, "rb") as f:
        data = f.read()
    return base64.b64encode(data).decode()
logo_light = load_base64_image("logo_black.PNG")
logo_dark = load_base64_image("logo_white.PNG")

# 前処理
def remove_strings(text: str) -> str:
    pattern = re.compile(r'【.*?】|[ＲR][ー-]\d+|\n|\t|\s+|■|＊')
    return pattern.sub('', text or "")

def normalize_output(text: str) -> str:
    text = (text or "").strip()
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    #text = re.sub(r"[a-zA-Z]+", "", text)
    return text.replace("\n", "").replace("\r", "").strip()

# 文字数
def count_chars(text: str) -> int:
    return len((text or "").replace("\n", "").replace("\r", ""))

def update_char_count():
    text = st.session_state.get("edited_ad", "")
    st.session_state["current_char_count"] = len(
        text.replace("\n", "").replace("\r", "")
    )

# Word保存
def create_docx_bytes(text):
    doc = Document()
    doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf

# HF 呼び出し
def _extract_message_text(choice) -> str:
    msg = getattr(choice, "message", None)
    if isinstance(msg, dict):
        return msg.get("content", "")
    return getattr(msg, "content", "")

def _call_chat(client, messages, max_tokens, temperature):
    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return _extract_message_text(resp.choices[0]).strip()
        except (ConnectTimeout, ReadTimeout):
            time.sleep(2 ** attempt)
        except HTTPError as e:
            if getattr(e.response, "status_code", 500) >= 500:
                time.sleep(2 ** attempt)
            else:
                raise
    return ""

# 文字数厳格化
def finalize_ad(text: str, target_chars: int) -> str:
    text = normalize_output(text)

    # 句点保証
    if not text.endswith("。"):
        text += "。"

    if len(text) <= target_chars:
        return text

    # 長い → 文末優先でカット
    cut = text[:target_chars]
    for i in range(len(cut) - 1, -1, -1):
        if cut[i] == "。":
            return cut[:i + 1]

    # 句点がなければ強制
    return cut[:-1] + "。"

def finalize_with_llm(client, system_prompt, ad, target_chars, max_tokens, temperature):
    length = len(ad)
    if length == target_chars and ad.endswith("。"):
        return ad

    prompt = (
        f"次の文章を、意味を変えずに自然な広告文として整形してください。\n"
        f"len()で数えて {target_chars} 文字ちょうどにしてください。\n"
        f"【条件】日本語のみ／固有名詞禁止／改行なし／文末は「。」\n\n"
        f"【元の文章（{length}文字）】\n{ad}\n\n"
        f"【修正後】"
    )

    new_ad = _call_chat(
        client,
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        max_tokens=max_tokens,
        temperature=temperature,
    )

    return normalize_output(new_ad) if new_ad else ad

# キーワード指定
def build_keyword_instruction(keywords: str):
    words = [w for w in re.split(r"[ 　]+", keywords.strip()) if w]
    if not words:
        return ""
    return f"以下のキーワードを必ずすべて1回以上含めてください。絶対に省略しないでください。文章の自然な位置に挿入してください：" + "、".join(words) + "。"

# 表現
def build_tone_instruction(tone: str) -> str:
    if tone == "やさしい":
        return (
            "・小学生でもすぐ理解できる、やさしい言葉を使う\n"
            "・難しい言葉や専門用語は使わない\n"
            "・一文を短めにして素直な文にする\n"
        )
    else:
        return (
            "・公の場に出しても問題ない表現にする\n"
            "・誤解を招く言い方や強すぎる表現は避ける\n"
        )

# 広告文生成
def generate_newspaper_ad_api(text, target_chars, keywords, tone, temperature=0.2):
    if not HF_TOKEN:
        raise RuntimeError("HUGGINGFACEHUB_API_TOKEN が設定されていません。")

    client = InferenceClient(model=MODEL_ID, token=HF_TOKEN, timeout=60)
    cleaned = remove_strings(text)
    tone_inst = build_tone_instruction(tone)
    keyword_inst = build_keyword_instruction(keywords)

    ad = _call_chat(
        client,
        [{"role": "user", "content": (
            f"次の原稿をもとに、テレビ番組の視聴を促す新聞広告文を作成してください。\n"
            f"・日本語のみ\n"
            f"・固有名詞禁止\n"
            f"・改行なし\n"
            f"・文末は「。」\n"
            f"・文章は {target_chars} トークン程度で書く\n\n"
            f"・読者が『この番組を見てみたい』と思うように書く\n"
            f"・番組の魅力を簡潔にまとめる\n"
            f"・最後に視聴を促す一言を入れる\n"
            f"・テレビの放送時間帯は昼なので「今夜」とは書かない\n"
            f"{tone_inst}\n"
            f"{keyword_inst}\n\n"
            f"【原稿】\n{cleaned}\n\n【広告文】"
        )}],
        max_tokens=int((target_chars + 30) * 3),
        temperature=temperature,
    )

    ad = normalize_output(ad)
    # ここで LLM による文字数調整を1回だけ行う
    system_prompt = "あなたは広告文の整形専門家です。"
    ad = finalize_with_llm(client, system_prompt, ad, target_chars, max_tokens=int(target_chars * 2.5) + 200, temperature=temperature,)
    #ad = finalize_ad(ad, target_chars)
    return ad

# Streamlit UI
def main():
    load_css("style.css")
    
    if "current_ad" not in st.session_state:
        st.session_state["current_ad"] = ""
    if "edited_ad" not in st.session_state:
        st.session_state["edited_ad"] = ""
    if "current_char_count" not in st.session_state:
        st.session_state["current_char_count"] = 0
    
    st.markdown(
        f'''<div class="logo-container"><img src="data:image/png;base64,{logo_light}" class="logo-light"><img src="data:image/png;base64,{logo_dark}" class="logo-dark"></div>''', unsafe_allow_html=True)

    option = st.sidebar.radio("入力方法を選択", ("テキスト", "ファイル"))
    text = ""

    if option == "テキスト":
        text = st.text_area("広告文にしたい原稿を入力してください", height=260)

    else:
        uploadfile = st.file_uploader("ファイルを選択", type=["txt", "docx"])
        if uploadfile is not None:
            try:
                if uploadfile.name.endswith(".txt"):
                    text = uploadfile.read().decode("utf-8", errors="ignore")
                elif uploadfile.name.endswith(".docx"):
                    doc = Document(uploadfile)
                    text = "\n".join([p.text for p in doc.paragraphs])
            except Exception as e:
                st.error(f"ファイルの読み込みに失敗しました: {e}")
                text = ""

    # 文字数指定
    target_chars = st.sidebar.number_input("文字数", min_value=10, max_value=500, value=120, step=1)
    
    # 文章表現選択
    tone = st.sidebar.radio("文章のスタイル", ["かたい", "やさしい"], horizontal=True)
    
    # キーワード指定
    keywords = st.sidebar.text_input("キーワード指定（スペース区切り）", value="")

    # 保存ファイル名
    filename = st.sidebar.text_input("保存するファイル名", value="newspaper")
    ext = st.sidebar.radio("保存形式", [".txt", ".docx"], horizontal=True)
    download = filename + ext

    # 要約生成    
    if st.button("広告文を生成"):
        try:
            if not text.strip():
                st.warning("原稿を入力してください。")
            else:
                with st.spinner("広告文を生成中..."):
                    ad = generate_newspaper_ad_api(text=text, target_chars=target_chars, keywords=keywords, tone=tone)

                    st.session_state["current_ad"] = ad
                    st.session_state["edited_ad"] = ad
                    st.session_state["current_char_count"] = len(ad)
       
        except Exception as e:
            st.error(f"エラーが発生しました: {e}")

    # ダウンロードボタン
    if st.session_state["current_ad"]:
        st.text_area("生成結果", key="edited_ad", on_change=update_char_count, height=200)
        st.markdown(f"文字数：{st.session_state['current_char_count']} 文字")
                
        final_text = st.session_state["edited_ad"]
        if ext == ".docx":
            file_data = create_docx_bytes(final_text)
            mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        else:
            file_data = final_text
            mime = "text/plain"
  
        st.download_button(
            label="ダウンロード",
            data=file_data,
            file_name=download,
            mime=mime
            )

# 実行
if __name__ == "__main__":
    main()
