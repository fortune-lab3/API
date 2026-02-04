# 目次
- [GitHub](#githubについて)
- [Hugging Face](#hugging-face-について)
- [Streamlitshare](#streamlit-cloud-について)

# GitHubについて
## アカウント作成
1. [GitHub](https://github.com)のサイトへアクセス
2. 右上の **Sign up** をクリック
3. メールアドレス、パスワード、ユーザーネームなどを入力し、**Create account** ボタンをクリックしてアカウントを作成

## リポジトリをコピー
1. [GitHub](https://github.com/fortune-lab3/PBL/)にアクセス
2. 右上の **Fork** ボタンをクリック
3. 右下の緑色 **Create Fork** ボタンをクリックして自分のリポジトリにコピー

# Hugging Face について
## アカウント作成
1. [Hugging Face](https://huggingface.co)のサイトへアクセス
2. 右上の **Sign Up** ボタンをクリック
3. メールアドレス、パスワード、ユーザーネームを入力して作成

## Hugging Face APIキーを取得
1. [Hugging Face](https://huggingface.co)にログイン
2. 右上の丸いアイコンをクリックし、**Setting** ボタンをクリック
3. 左側にある **Access Tokens** をクリック
4. 右上にある **+ Create new token** をクリック
5. Token type を **Read** にして Token name に任意の名前を入力
6. **Create token** ボタンをクリックしてAPIキーを作成
7. 表示される **hf_** からはじまるAPIキーをコピー（このときにしか表示されないので絶対にコピーしておく）
8. APIキーは絶対に外部に公開しない

# Streamlit Cloud について
## アカウント作成
1. [Streamlit Cloud](https://share.streamlit.io/)にアクセス
2. **Continue to sing-in** ボタンをクリック
3. **GitHubで続行** を選択し、連携を許可

## アプリを作成
1. [share.streamlit](https://share.streamlit.io/)にアクセス
2. 右上の **Create app** をクリック
3. **Deploy a public app from GitHub** を選択
4. Repositoryに **アカウント名/PBL**、Branchに **main**、Main file pathに **app.py** を選択（枠をクリックすると候補がでてきます）
5. App URLに任意のURL名を入力（これがURL
6. **Deploy** をクリックしてアプリを作成

## APIキー設定
1. [share.streamlit](https://share.streamlit.io/)にアクセス
2. 作成したアプリ（pbl・main・app.py）の右端にある︙をクリックし、**Settings** をクリック
3. 左側にある **Secrets** をクリック
4. 枠の中に ```HUGGINGFACEHUB_API_TOKEN = "取得したAPIキー" ``` を入力
5. 右下の **Save changes** をクリックして保存
6. これで、作成したアプリ（pbl・main・app.py）をクリックすると使えるようになります
7. 一定期間アクセスしなかったらアプリがスリープ状態になるので、表示される ボタンをクリックして少し待てば起動します
