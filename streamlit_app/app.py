"""
AI X Bot 管理画面 (Streamlit)
- 📊 ダッシュボード: 最新の実行履歴・次回実行予定・成功率
- ▶️ 手動実行: workflow_dispatch をトリガー（DRY RUN / 本番）
- 👀 プレビュー: 最新の実行で生成されたレポート（投稿予定の中身）を表示
"""

import os
import io
import json
import zipfile
from datetime import datetime, timezone, timedelta

import requests
import streamlit as st

# ========================================
# 設定
# ========================================

REPO = "zenosynead-star/ai-x-bot"
WORKFLOW_FILE = "daily.yml"
API_BASE = f"https://api.github.com/repos/{REPO}"
JST = timezone(timedelta(hours=9))

st.set_page_config(
    page_title="AI X Bot 管理画面",
    page_icon="🤖",
    layout="wide",
)

# ========================================
# 認証
# ========================================

def get_token():
    """Streamlit Secrets またはローカル環境変数から GITHUB_TOKEN を取得"""
    try:
        return st.secrets["GITHUB_TOKEN"]
    except Exception:
        return os.getenv("GITHUB_TOKEN")


GITHUB_TOKEN = get_token()
if not GITHUB_TOKEN:
    st.error(
        "❌ GITHUB_TOKEN が設定されていません。\n\n"
        "**ローカル実行時:** `streamlit_app/.streamlit/secrets.toml` に `GITHUB_TOKEN = \"ghp_...\"` を記載\n\n"
        "**Streamlit Cloud:** App settings → Secrets で同じ内容を登録"
    )
    st.stop()

# ========================================
# GitHub API ヘルパー
# ========================================

def gh_api(method: str, endpoint: str, **kwargs):
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    url = f"{API_BASE}{endpoint}"
    return requests.request(method, url, headers=headers, timeout=30, **kwargs)


def fmt_jst(iso_str: str) -> str:
    if not iso_str:
        return "-"
    dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    return dt.astimezone(JST).strftime("%m-%d %H:%M")


def status_emoji(status: str, conclusion: str | None) -> str:
    if status != "completed":
        return "🔄"
    return {"success": "✅", "failure": "❌", "cancelled": "⏹️"}.get(conclusion or "", "❓")


# ========================================
# サイドバー
# ========================================

st.sidebar.title("🤖 AI X Bot")
st.sidebar.markdown(f"**Repo:** [{REPO}](https://github.com/{REPO})")
st.sidebar.markdown(f"**Schedule:** 毎日 JST 07:00")
st.sidebar.divider()

page = st.sidebar.radio(
    "ページ",
    ["📊 ダッシュボード", "▶️ 手動実行", "👀 プレビュー"],
)

st.sidebar.divider()
if st.sidebar.button("🔄 キャッシュをクリア"):
    st.cache_data.clear()
    st.rerun()

# ========================================
# ページ: ダッシュボード
# ========================================

if page == "📊 ダッシュボード":
    st.title("📊 ダッシュボード")

    # 次回実行予定（毎日 JST 07:00）
    now_jst = datetime.now(JST)
    next_run = now_jst.replace(hour=7, minute=0, second=0, microsecond=0)
    if now_jst >= next_run:
        next_run += timedelta(days=1)
    delta = next_run - now_jst
    hours, rem = divmod(int(delta.total_seconds()), 3600)
    minutes = rem // 60

    # 最新の実行履歴を取得
    with st.spinner("実行履歴を取得中..."):
        r = gh_api("GET", f"/actions/workflows/{WORKFLOW_FILE}/runs?per_page=20")

    if r.status_code != 200:
        st.error(f"実行履歴取得エラー: {r.status_code} {r.text}")
        st.stop()

    runs = r.json().get("workflow_runs", [])

    col1, col2, col3 = st.columns(3)
    col1.metric("次回自動実行", next_run.strftime("%m-%d 07:00"), f"あと {hours}h{minutes}m")
    col2.metric("実行履歴", f"{len(runs)} 件")
    success_count = sum(1 for run in runs if run.get("conclusion") == "success")
    col3.metric("成功", f"{success_count}/{len(runs)}" if runs else "-")

    st.divider()
    st.subheader("実行履歴（最新20件）")

    if not runs:
        st.info("実行履歴がありません。")
    else:
        for run in runs:
            run_id = run["id"]
            emoji = status_emoji(run["status"], run.get("conclusion"))
            trigger = run["event"]
            created = fmt_jst(run["created_at"])
            duration = ""
            if run.get("updated_at") and run["status"] == "completed":
                start = datetime.fromisoformat(run["created_at"].replace("Z", "+00:00"))
                end = datetime.fromisoformat(run["updated_at"].replace("Z", "+00:00"))
                duration = f"{int((end-start).total_seconds())}s"

            cols = st.columns([1, 3, 3, 3, 2])
            cols[0].markdown(f"### {emoji}")
            cols[1].markdown(f"**#{run_id}**")
            cols[2].markdown(f"📅 {created}")
            cols[3].markdown(f"🎯 `{trigger}` · {duration}")
            cols[4].markdown(f"[詳細 →]({run['html_url']})")

# ========================================
# ページ: 手動実行
# ========================================

elif page == "▶️ 手動実行":
    st.title("▶️ 手動実行")
    st.markdown(
        "ボタンを押すと GitHub Actions で `daily.yml` の `workflow_dispatch` がトリガーされます。"
        "実行完了まで約30秒〜1分かかります。"
    )

    dry_run = st.toggle("DRY RUN（投稿せず動作確認のみ）", value=True)

    if dry_run:
        st.success("✅ **DRY RUN モード**：実際には投稿されません。生成内容のチェックだけ。")
    else:
        st.warning("⚠️ **本番モード**：実際にXに投稿されます（オリジナル投稿3件＝コスト約7円）。")

    if st.button("🚀 今すぐ実行", type="primary", use_container_width=True):
        with st.spinner("workflow_dispatch をトリガー中..."):
            r = gh_api(
                "POST",
                f"/actions/workflows/{WORKFLOW_FILE}/dispatches",
                json={"ref": "main", "inputs": {"dry_run": str(dry_run).lower()}},
            )
        if r.status_code == 204:
            st.success("✅ 実行をトリガーしました！数秒後に「📊 ダッシュボード」で進捗確認できます。")
            st.balloons()
        else:
            st.error(f"❌ エラー: {r.status_code} {r.text}")

# ========================================
# ページ: プレビュー
# ========================================

elif page == "👀 プレビュー":
    st.title("👀 投稿プレビュー")
    st.markdown(
        "選択した実行で生成された **HTML レポート** と **トレンドデータ** を表示します。"
    )

    with st.spinner("実行履歴を取得中..."):
        r = gh_api("GET", f"/actions/workflows/{WORKFLOW_FILE}/runs?status=success&per_page=10")

    if r.status_code != 200:
        st.error(f"エラー: {r.status_code}")
        st.stop()

    runs = r.json().get("workflow_runs", [])
    if not runs:
        st.info("成功した実行がまだありません。")
        st.stop()

    options = {
        f"#{run['id']}  ·  {fmt_jst(run['created_at'])}  ·  {run['event']}": run["id"]
        for run in runs
    }
    selected_label = st.selectbox("実行を選択", list(options.keys()))
    selected_run_id = options[selected_label]

    with st.spinner("artifact を確認中..."):
        r = gh_api("GET", f"/actions/runs/{selected_run_id}/artifacts")

    if r.status_code != 200:
        st.error(f"artifact 取得エラー: {r.status_code}")
        st.stop()

    artifacts = r.json().get("artifacts", [])
    if not artifacts:
        st.info("この実行に artifact がありません（古い実行で削除されている可能性）。")
        st.stop()

    artifact = artifacts[0]
    st.caption(f"📦 artifact: `{artifact['name']}`（{artifact['size_in_bytes']/1024:.1f} KB）")

    with st.spinner("レポートをダウンロード中..."):
        r = gh_api(
            "GET",
            f"/actions/artifacts/{artifact['id']}/zip",
            allow_redirects=True,
            stream=False,
        )

    if r.status_code != 200:
        st.error(f"ダウンロードエラー: {r.status_code}")
        st.stop()

    try:
        z = zipfile.ZipFile(io.BytesIO(r.content))
    except zipfile.BadZipFile:
        st.error("artifact が zip 形式ではありません。")
        st.stop()

    html_files = [n for n in z.namelist() if n.endswith(".html")]
    json_files = [n for n in z.namelist() if n.endswith(".json")]

    if html_files:
        latest_html = max(html_files)
        html_content = z.read(latest_html).decode("utf-8")
        st.subheader(f"📄 レポート: `{latest_html}`")
        st.components.v1.html(html_content, height=900, scrolling=True)

    if json_files:
        st.divider()
        st.subheader("📋 収集したトレンドデータ")
        for jf in json_files:
            with st.expander(f"`{jf}`"):
                try:
                    data = json.loads(z.read(jf).decode("utf-8"))
                    st.json(data)
                except Exception as e:
                    st.error(f"パースエラー: {e}")
