"""
AI X Bot 管理画面 (Streamlit)
- 📊 ダッシュボード: 実行履歴・次回実行予定・成功率
- ▶️ 手動実行: workflow_dispatch をトリガー（DRY RUN / 本番）
- 📝 投稿プレビュー: 次回投稿される文面を DRY RUN で生成して表示
- 💬 返信履歴: 過去の返信試行と結果（403制限の追跡）
- ⏰ スケジュール設定: daily.yml の cron を Web UI から書き換え
"""

import os
import io
import re
import json
import base64
import zipfile
from datetime import datetime, timezone, timedelta

import requests
import streamlit as st

# ========================================
# 設定
# ========================================

REPO = "zenosynead-star/ai-x-bot"
WORKFLOW_FILE = "daily.yml"
WORKFLOW_PATH = ".github/workflows/daily.yml"
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
    try:
        return st.secrets["GITHUB_TOKEN"]
    except Exception:
        return os.getenv("GITHUB_TOKEN")


GITHUB_TOKEN = get_token()
if not GITHUB_TOKEN:
    st.error(
        "❌ GITHUB_TOKEN が設定されていません。\n\n"
        "**ローカル:** `streamlit_app/.streamlit/secrets.toml` に `GITHUB_TOKEN = \"ghp_...\"` を記載\n\n"
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
    return requests.request(method, f"{API_BASE}{endpoint}", headers=headers, timeout=30, **kwargs)


def fmt_jst(iso_str: str) -> str:
    if not iso_str:
        return "-"
    dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    return dt.astimezone(JST).strftime("%m-%d %H:%M")


def fmt_jst_full(iso_str: str) -> str:
    if not iso_str:
        return "-"
    dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    return dt.astimezone(JST).strftime("%Y-%m-%d %H:%M")


def status_emoji(status: str, conclusion):
    if status != "completed":
        return "🔄"
    return {"success": "✅", "failure": "❌", "cancelled": "⏹️"}.get(conclusion or "", "❓")


@st.cache_data(ttl=60)
def get_workflow_runs(per_page: int = 30):
    r = gh_api("GET", f"/actions/workflows/{WORKFLOW_FILE}/runs?per_page={per_page}")
    return r.json().get("workflow_runs", []) if r.ok else []


@st.cache_data(ttl=600)
def get_artifact_for_run(run_id: int):
    r = gh_api("GET", f"/actions/runs/{run_id}/artifacts")
    if not r.ok:
        return None
    arts = r.json().get("artifacts", [])
    return arts[0] if arts else None


@st.cache_data(ttl=600)
def download_artifact_zip(artifact_id: int):
    r = gh_api("GET", f"/actions/artifacts/{artifact_id}/zip", allow_redirects=True)
    return r.content if r.ok else None


def get_artifact_contents(run_id: int) -> dict:
    """run の artifact をDLして {filename: bytes} で返す"""
    art = get_artifact_for_run(run_id)
    if not art:
        return {}
    data = download_artifact_zip(art["id"])
    if not data:
        return {}
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
        return {n: z.read(n) for n in z.namelist()}
    except zipfile.BadZipFile:
        return {}


def parse_history(contents: dict) -> dict | None:
    """contents から最新の history JSON を取得してパースする"""
    history_files = sorted([n for n in contents if n.startswith("history/") and n.endswith(".json")])
    if not history_files:
        return None
    try:
        return json.loads(contents[history_files[-1]].decode("utf-8"))
    except Exception:
        return None

# ========================================
# サイドバー
# ========================================

st.sidebar.title("🤖 AI X Bot")
st.sidebar.markdown(f"**Repo:** [{REPO}](https://github.com/{REPO})")
st.sidebar.divider()

page = st.sidebar.radio(
    "ページ",
    [
        "📊 ダッシュボード",
        "▶️ 手動実行",
        "📝 投稿プレビュー",
        "💬 返信履歴",
        "⏰ スケジュール設定",
    ],
)

st.sidebar.divider()
if st.sidebar.button("🔄 キャッシュをクリア", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

# ========================================
# 📊 ダッシュボード
# ========================================

if page == "📊 ダッシュボード":
    st.title("📊 ダッシュボード")

    with st.spinner("実行履歴を取得中..."):
        runs = get_workflow_runs(per_page=20)

    # 次回実行予定（最新の cron 設定から計算したいが、簡略化のため JST 07:00 固定表示。実際は ⏰ で確認）
    now_jst = datetime.now(JST)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("総実行数", f"{len(runs)} 件")
    success_count = sum(1 for run in runs if run.get("conclusion") == "success")
    col2.metric("成功", f"{success_count}/{len(runs)}" if runs else "-")
    dry_runs = sum(1 for run in runs if run.get("event") == "workflow_dispatch")
    col3.metric("手動実行", f"{dry_runs} 件")
    scheduled = sum(1 for run in runs if run.get("event") == "schedule")
    col4.metric("自動実行", f"{scheduled} 件")

    st.divider()
    st.subheader("実行履歴（最新20件）")

    if not runs:
        st.info("実行履歴がありません。")
    else:
        for run in runs:
            run_id = run["id"]
            emoji = status_emoji(run["status"], run.get("conclusion"))
            trigger = run["event"]
            created = fmt_jst_full(run["created_at"])
            duration = ""
            if run.get("updated_at") and run["status"] == "completed":
                start = datetime.fromisoformat(run["created_at"].replace("Z", "+00:00"))
                end = datetime.fromisoformat(run["updated_at"].replace("Z", "+00:00"))
                duration = f"{int((end - start).total_seconds())}s"

            cols = st.columns([1, 3, 3, 3, 2])
            cols[0].markdown(f"### {emoji}")
            cols[1].markdown(f"**#{run_id}**")
            cols[2].markdown(f"📅 {created}")
            cols[3].markdown(f"🎯 `{trigger}` · {duration}")
            cols[4].markdown(f"[詳細 →]({run['html_url']})")

# ========================================
# ▶️ 手動実行
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
            st.cache_data.clear()
            st.balloons()
        else:
            st.error(f"❌ エラー: {r.status_code} {r.text}")

# ========================================
# 📝 投稿プレビュー
# ========================================

elif page == "📝 投稿プレビュー":
    st.title("📝 投稿プレビュー")
    st.markdown(
        "「最新を生成」を押すと DRY RUN を実行し、**次回 cron で投稿される予定の文面**と同じ生成ロジックで"
        "プレビューを作ります（実際には投稿しません）。"
    )

    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("🔄 最新を生成", type="primary", use_container_width=True):
            r = gh_api(
                "POST",
                f"/actions/workflows/{WORKFLOW_FILE}/dispatches",
                json={"ref": "main", "inputs": {"dry_run": "true"}},
            )
            if r.status_code == 204:
                st.success("生成を開始。約1分後にこのページを再読込してください。")
                st.cache_data.clear()
            else:
                st.error(f"エラー: {r.status_code}")

    with col1:
        st.caption("最新の DRY RUN 結果を表示します。新しく生成した場合は完了まで約1分待ってから再読込。")

    # 最新の DRY RUN を探す
    runs = get_workflow_runs(per_page=30)

    # event が workflow_dispatch の中から最新成功を取得（cron実行（DRY_RUN=false）はスキップ）
    candidates = [
        r for r in runs
        if r.get("conclusion") == "success" and r.get("event") == "workflow_dispatch"
    ]

    if not candidates:
        st.info("DRY RUN の実行履歴がまだありません。「🔄 最新を生成」ボタンで作成してください。")
        st.stop()

    options = {
        f"#{r['id']}  ·  {fmt_jst_full(r['created_at'])}": r["id"]
        for r in candidates
    }
    selected_label = st.selectbox("表示する実行を選択", list(options.keys()))
    selected_run_id = options[selected_label]

    with st.spinner("生成結果を取得中..."):
        contents = get_artifact_contents(selected_run_id)

    if not contents:
        st.warning("この実行の artifact が取得できませんでした。古い実行で削除されている可能性。")
        st.stop()

    history = parse_history(contents)

    if history:
        st.caption(
            f"🧪 DRY RUN: {history.get('dry_run', '?')}  ·  "
            f"生成時刻: {fmt_jst_full(history.get('timestamp', ''))}"
        )

        # オリジナル投稿
        posts = history.get("posts", [])
        st.subheader(f"📤 オリジナル投稿（{len(posts)}件）")
        if not posts:
            st.info("オリジナル投稿の履歴がありません。")
        for i, p in enumerate(posts, 1):
            style_map = {
                "breaking": "🚨 速報型",
                "tips": "📚 Tips型",
                "alert": "⚠️ 気づき型",
                "story": "💬 共感型",
            }
            style_label = style_map.get(p.get("style", ""), p.get("style", "?"))
            with st.container(border=True):
                head_cols = st.columns([4, 2, 2])
                head_cols[0].markdown(f"**[{i}/{len(posts)}]** {style_label}")
                head_cols[1].caption(f"X換算 {p.get('twitter_count', '?')}文字")
                head_cols[2].caption("✅ 生成成功" if p.get("post_text") else "❌ 失敗")
                st.code(p.get("post_text", "（生成失敗）"), language=None)
                if p.get("news_title"):
                    st.caption(f"📰 元ニュース: {p['news_title']}")

        # 返信
        replies = history.get("replies", [])
        st.subheader(f"💬 返信文（{len(replies)}件）")
        if not replies:
            st.info("返信の履歴がありません。")
        for i, r in enumerate(replies, 1):
            success = r.get("success")
            msg = r.get("message") or ""
            if success:
                badge = "✅ 送信成功"
            elif "返信制限" in msg:
                badge = "⛔ 返信制限"
            elif "DRY_RUN" in msg:
                badge = "🧪 DRY RUN"
            else:
                badge = f"❌ {msg[:30]}"
            with st.container(border=True):
                head_cols = st.columns([4, 2])
                head_cols[0].markdown(f"**[{i}/{len(replies)}]** → `{r.get('original_account', '?')}`")
                head_cols[1].caption(badge)
                st.code(r.get("reply_text", "（生成失敗）"), language=None)
                if r.get("tweet_url"):
                    st.caption(f"[元ツイートを開く →]({r['tweet_url']})")
    else:
        # フォールバック: HTML レポートを表示
        html_files = [n for n in contents if n.endswith(".html")]
        if html_files:
            latest_html = max(html_files)
            html_content = contents[latest_html].decode("utf-8")
            st.subheader(f"📄 レポート: `{latest_html}`")
            st.components.v1.html(html_content, height=900, scrolling=True)
        else:
            st.warning("この実行には history JSON も HTML レポートもありません。")

# ========================================
# 💬 返信履歴
# ========================================

elif page == "💬 返信履歴":
    st.title("💬 返信履歴")
    st.markdown("過去の実行から自動返信の試行記録を集計します。403返信制限の追跡用。")

    max_runs = st.slider("集計対象の実行数", min_value=5, max_value=30, value=15, step=5)

    with st.spinner(f"最新{max_runs}件の実行を集計中..."):
        runs = get_workflow_runs(per_page=max_runs)

    all_replies = []
    processed_runs = 0

    progress = st.progress(0, "履歴を読み込み中...")
    for idx, run in enumerate(runs):
        progress.progress((idx + 1) / max(len(runs), 1), f"履歴 {idx+1}/{len(runs)} を確認中")
        if run.get("conclusion") != "success":
            continue
        contents = get_artifact_contents(run["id"])
        history = parse_history(contents)
        if not history:
            continue
        processed_runs += 1
        run_time = history.get("timestamp", run.get("created_at"))
        is_dry = history.get("dry_run", False)
        for r in history.get("replies", []):
            success = r.get("success")
            msg = r.get("message") or ""
            if success:
                result_label = "✅ 成功"
            elif "返信制限" in msg:
                result_label = "⛔ 返信制限"
            elif "DRY_RUN" in msg:
                result_label = "🧪 DRY RUN"
            else:
                result_label = f"❌ エラー"
            all_replies.append({
                "実行日時": fmt_jst_full(run_time),
                "モード": "🧪 DRY" if is_dry else "🔴 本番",
                "送信先": r.get("original_account") or "-",
                "結果": result_label,
                "本文": (r.get("reply_text") or "")[:50] + ("..." if len(r.get("reply_text") or "") > 50 else ""),
                "詳細": (r.get("message") or "")[:80],
            })

    progress.empty()

    if not all_replies:
        st.info(
            "返信履歴が見つかりません。\n\n"
            "新機能を追加した直後なので、次回の実行から記録が始まります。"
            "「▶️ 手動実行」で DRY RUN を1回走らせれば最初の記録ができます。"
        )
        st.stop()

    # サマリー
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("集計対象", f"{processed_runs}/{len(runs)} run")
    col2.metric("返信試行数", f"{len(all_replies)} 件")
    success = sum(1 for r in all_replies if r["結果"] == "✅ 成功")
    restricted = sum(1 for r in all_replies if r["結果"] == "⛔ 返信制限")
    col3.metric("成功", success)
    col4.metric("返信制限 (403)", restricted)

    st.divider()
    st.subheader("返信ログ")
    st.dataframe(
        all_replies,
        use_container_width=True,
        hide_index=True,
    )

# ========================================
# ⏰ スケジュール設定
# ========================================

elif page == "⏰ スケジュール設定":
    st.title("⏰ スケジュール設定")
    st.markdown(
        "GitHub Actions の cron 実行時刻を変更します。"
        "保存すると `.github/workflows/daily.yml` が直接書き換えられ、main ブランチに commit されます。"
    )

    # 現在の yml を取得
    r = gh_api("GET", f"/contents/{WORKFLOW_PATH}")
    if not r.ok:
        st.error(f"yml 取得エラー: {r.status_code} {r.text}")
        st.stop()

    yml_data = r.json()
    yml_text = base64.b64decode(yml_data["content"]).decode("utf-8")

    # cron 行をパース
    m = re.search(r"-\s+cron:\s+'(\S+)'", yml_text)
    if not m:
        st.error("cron 行が見つかりませんでした")
        st.code(yml_text)
        st.stop()

    current_cron = m.group(1)
    parts = current_cron.split()
    try:
        current_minute = int(parts[0])
        current_utc_hour = int(parts[1])
    except (ValueError, IndexError):
        st.error(f"cron 式のパースに失敗: {current_cron}")
        st.stop()

    current_jst_hour = (current_utc_hour + 9) % 24

    st.info(
        f"**現在の cron:** `{current_cron}`\n\n"
        f"**実行時刻:** 毎日 JST **{current_jst_hour:02d}:{current_minute:02d}** (UTC {current_utc_hour:02d}:{current_minute:02d})"
    )

    st.divider()
    st.subheader("新しい実行時刻")

    col1, col2 = st.columns(2)
    new_hour = col1.number_input("JST 時 (0-23)", value=current_jst_hour, min_value=0, max_value=23, step=1)
    new_minute = col2.number_input("JST 分 (0-59)", value=current_minute, min_value=0, max_value=59, step=1)

    new_utc_hour = (new_hour - 9) % 24
    new_cron = f"{new_minute} {new_utc_hour} * * *"

    st.caption(f"新しい cron 式: `{new_cron}` → 毎日 JST {new_hour:02d}:{new_minute:02d}")

    if new_cron == current_cron:
        st.caption("現在の設定と同じです。")
    else:
        if st.button(
            f"💾 cron を `{new_cron}` に更新（GitHub に commit）",
            type="primary",
            use_container_width=True,
        ):
            new_yml = re.sub(r"-\s+cron:\s+'\S+'", f"- cron: '{new_cron}'", yml_text, count=1)
            put_payload = {
                "message": f"Update cron to JST {new_hour:02d}:{new_minute:02d} (UTC {new_utc_hour:02d}:{new_minute:02d})",
                "content": base64.b64encode(new_yml.encode("utf-8")).decode(),
                "sha": yml_data["sha"],
            }
            with st.spinner("GitHub に commit 中..."):
                resp = gh_api("PUT", f"/contents/{WORKFLOW_PATH}", json=put_payload)
            if resp.ok:
                st.success(
                    f"✅ 更新しました！次回実行は **JST {new_hour:02d}:{new_minute:02d}** から有効になります。\n\n"
                    f"Commit: [{resp.json().get('commit', {}).get('sha', '')[:7]}]({resp.json().get('commit', {}).get('html_url', '#')})"
                )
                st.cache_data.clear()
            else:
                st.error(f"❌ 更新エラー: {resp.status_code} {resp.text}")

    st.divider()
    with st.expander("📄 現在の daily.yml 全文を見る"):
        st.code(yml_text, language="yaml")
