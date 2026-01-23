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
logo_light = load_base64_image("img/logo_black.PNG")
logo_dark = load_base64_image("img/logo_white.PNG")

# 前処理
def remove_strings(text: str) -> str:
    pattern = re.compile(r'【.*?】|[ＲR][ー-]\d+|■|＊')
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
def finalize_with_llm(client, system_prompt, ad, target_chars, max_tokens, temperature, keywords, tone):
    ad = normalize_output(ad)
    tone_inst = build_tone_instruction(tone)
    kw_list = split_keywords(keywords)
    kw_text = "、".join(kw_list)

    kw_constraint = ""
    if kw_list:
        kw_constraint = (
            f"次のキーワードは必ずすべてそのまま残してください：{kw_text}\n"
            f"これらの削除・言い換え・表記変更は禁止です。\n"
        )

    for _ in range(2):
        current_len = len(ad)
        diff = target_chars - current_len

        if abs(diff) <= 5 and ad.endswith("。"):
            return ad

        if diff > 0:
            adjust_instruction = f"現在 {current_len}文字なので、{diff} 文字分だけ内容を自然に補ってください。"
        else:
            adjust_instruction = f"現在 {current_len}文字なので、{abs(diff)} 文字分だけ内容を自然に削ってください。"

        prompt = (
            f"次の文章の意味と構成をできるだけ変えずに、文字数だけを調整してください。\n"
            f"{kw_constraint}"
            f"{tone_inst}"
            f"{adjust_instruction}\n"
            f"文字数が {target_chars} ±5 の範囲に入っていない場合は、必ず文章を修正して再生成\n"
            f"【元の文章】\n{ad}\n\n"
            f"【整形後（{target_chars}文字）】"
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

        if not new_ad:
            break

        ad = normalize_output(new_ad)

    return ad

# キーワード指定
def split_keywords(keywords: str):
    return [w for w in re.split(r"[ 　]+", keywords.strip()) if w]

def build_keyword_instruction(keywords: str):
    words = split_keywords(keywords)
    if not words:
        return ""
    return (
        "【キーワードの扱いルール】\n"
        "・キーワードは各1回だけ使用すること\n"
        "・2回以上繰り返すことは禁止\n"
        "・強調や説明のための再使用も禁止\n"
        "・キーワードの意味を推測しない\n"
        "・ストーリー化しない\n"
        "・キーワード同士を関連づけない\n"
        "・単語として自然な位置に挿入するだけ\n"
        "・削除・言い換え・表記ゆれは禁止\n"
        f"以下のキーワードを必ずすべて1回だけ含めること：{ '、'.join(words) }。"
    )

# 表現
def build_tone_instruction(tone: str) -> str:
    if tone == "やさしい":
        return (
            "・漢語（熟語）を避け、和語（訓読みの言葉）を優先して使うこと\n"
            "・ひらがなの比率を上げ、見た目の威圧感をなくすこと\n"
            "・専門用語や難しい概念は、身近な例えに置き換えること\n"
        )
    else:
        return ""

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
            f"次の原稿をもとに、新聞のラテ欄風の広告文を書いてください。\n"
            f"文字数は日本語でちょうど {target_chars} 文字\n"
            f"次にある文体ルールを厳密に守ってください。\n"
            f"・文は必ず「誰が・どこで・何をするか」の形で書く\n"
            f"・文末には視聴者の興味を引くフックを必ず入れる\n"
            f"・感情やインパクトのある言葉を使う\n"
            f"・季節感やテーマがあれば冒頭に入れる\n"
            f"・応募やプレゼントキャンペーンについては書かない\n"
            f"【条件】日本語のみ・改行なし\n"
            f"{tone_inst}\n"
            f"{keyword_inst}\n\n"
            #f"文字数が {target_chars} ±5 の範囲に入っていない場合は、文章を修正して再生成してください。\n"
            f"生成文のみを出力・捕捉などは出力しない\n"
            f"【原稿】\n{cleaned}\n\n【広告文】"
        )}],
        max_tokens=int((target_chars) * 1.2),
        temperature=temperature,
    )

    ad = normalize_output(ad)
    # 文字数調整
    system_prompt = "あなたは日本語文章の文字数を正確に調整する編集者です。"
    ad = finalize_with_llm(client, system_prompt, ad, target_chars, max_tokens=int(target_chars * 2), temperature=0.1, keywords=keywords, tone=tone)

    return ad

# Streamlit UI
def main():
    st.set_page_config(page_title="南海ことば工房", page_icon="img/favicon.PNG")
    load_css("style.css")
    
    if "current_ad" not in st.session_state:
        st.session_state["current_ad"] = ""
    if "edited_ad" not in st.session_state:
        st.session_state["edited_ad"] = ""
    if "current_char_count" not in st.session_state:
        st.session_state["current_char_count"] = 0
    
    st.markdown(
        f'<div class="logo-container"><img src="data:image/png;base64,{logo_light}" class="logo-light"><img src="data:image/png;base64,{logo_dark}" class="logo-dark"></div>', unsafe_allow_html=True)

    option = st.sidebar.radio("入力方法を選択", ("テキスト", "ファイル"))
    text = ""

    if option == "テキスト":
        text = st.text_area("広告文にしたい原稿を入力してください", height=260)
        text = text.strip().replace("\r", "")
        text = text.replace("　", " ")
        text = re.sub(r"\s+", " ", text)

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
    target_chars = st.sidebar.number_input("文字数", min_value=10, max_value=500, value=100, step=1)
    
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
