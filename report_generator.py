"""
HTMLレポート生成モジュール
毎日のアクションプランをブラウザで見やすく表示する
"""

import os
import webbrowser
from datetime import datetime
from pathlib import Path


def generate_report(replies: list, original_posts: list, best_times: list,
                    reply_results: list = None, post_results: list = None) -> str:
    """
    アクションプランのHTMLレポートを生成してブラウザで開く

    Returns:
        保存したHTMLファイルのパス
    """
    now = datetime.now()
    date_str = now.strftime("%Y年%m月%d日")
    time_str = now.strftime("%H:%M")

    # 返信カードのHTML生成
    reply_cards = ""
    for i, r in enumerate(replies, 1):
        score = r.get("engagement_score", 0)
        tweet_url = r.get("tweet_url") or ""
        open_btn = f'<a class="open-tweet-btn" href="{tweet_url}" target="_blank">🐦 ツイートを開く</a>' if tweet_url else ""

        res = (reply_results[i-1] if reply_results and i-1 < len(reply_results) else None)
        if res:
            if res.get("url"):
                status_badge = f'<a class="posted-badge" href="{res["url"]}" target="_blank">✅ 投稿済み →</a>'
            elif res.get("message") == "DRY_RUN":
                status_badge = '<span class="dry-badge">🔵 DRY RUN</span>'
            elif "REPLY_RESTRICTED" in str(res.get("message", "")) or "スキップ" in str(res.get("message", "")):
                status_badge = '<span class="manual-badge">📋 手動返信 →</span>'
            else:
                status_badge = f'<span class="error-badge">❌ {res.get("message","エラー")}</span>'
        else:
            status_badge = '<span class="manual-badge">📋 手動返信 →</span>'

        reply_cards += f"""
        <div class="card reply-card">
            <div class="card-header">
                <span class="badge badge-reply">返信 {i}/{len(replies)}</span>
                <span class="account">→ {r['original_account']}</span>
                <span class="score">🔥 エンゲージメント {score:,}</span>
                {status_badge}
            </div>
            <div class="original-post">
                <div class="label">元の投稿</div>
                <div class="original-text">{r['original_text'].replace(chr(10), '<br>')}</div>
            </div>
            <div class="reply-content">
                <div class="label">返信テキスト</div>
                <div class="post-text" id="reply-{i}">{r['reply']}</div>
                <div class="reply-actions">
                    <button class="copy-btn" onclick="copyText('reply-{i}', this)">
                        📋 コピー
                    </button>
                    {open_btn}
                </div>
            </div>
        </div>"""

    # 投稿カードのHTML生成
    style_names = {
        "breaking": "🚨 速報型",
        "tips": "📚 保存版Tips",
        "alert": "⚠️ 警告型",
        "story": "💬 共感型",
    }
    post_time_icons = ["🕗", "🕛", "🕘"]

    post_cards = ""
    for i, item in enumerate(original_posts, 1):
        style_label = style_names.get(item["style"], item["style"])
        time_label = best_times[i - 1] if i - 1 < len(best_times) else ""
        icon = post_time_icons[i - 1] if i - 1 < len(post_time_icons) else "🕐"
        post_text_html = item["post"].replace("\n", "<br>")

        res = (post_results[i-1] if post_results and i-1 < len(post_results) else None)
        if res:
            if res.get("url"):
                status_badge = f'<a class="posted-badge" href="{res["url"]}" target="_blank">✅ 投稿済み →</a>'
            elif res.get("message") == "DRY_RUN":
                status_badge = '<span class="dry-badge">🔵 DRY RUN</span>'
            else:
                status_badge = f'<span class="error-badge">❌ {res.get("message","エラー")}</span>'
        else:
            status_badge = '<span class="manual-badge">📋 手動投稿</span>'

        post_cards += f"""
        <div class="card post-card">
            <div class="card-header">
                <span class="badge badge-post">投稿 {i}/3</span>
                <span class="style-tag">{style_label}</span>
                <span class="time-tag">{icon} {time_label}</span>
                <span class="char-count">X換算 {item.get('twitter_count', item['char_count'])}/270文字</span>
                {status_badge}
            </div>
            <div class="post-content">
                <div class="post-text" id="post-{i}">{post_text_html}</div>
                <button class="copy-btn" onclick="copyText('post-{i}', this)">
                    📋 コピー
                </button>
            </div>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI X Bot — {date_str}のアクションプラン</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Hiragino Sans", sans-serif;
            background: #0f0f0f;
            color: #e8e8e8;
            min-height: 100vh;
            padding: 24px 16px;
        }}

        .container {{ max-width: 760px; margin: 0 auto; }}

        /* ヘッダー */
        .header {{
            text-align: center;
            margin-bottom: 32px;
        }}
        .header h1 {{
            font-size: 22px;
            font-weight: 700;
            color: #fff;
            margin-bottom: 6px;
        }}
        .header .date {{
            color: #888;
            font-size: 14px;
        }}
        .header .tagline {{
            margin-top: 10px;
            font-size: 13px;
            color: #1d9bf0;
        }}

        /* セクションタイトル */
        .section-title {{
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 16px;
            font-weight: 700;
            color: #fff;
            margin: 32px 0 14px;
            padding-bottom: 8px;
            border-bottom: 1px solid #2a2a2a;
        }}
        .section-title .step {{
            background: #1d9bf0;
            color: #fff;
            font-size: 11px;
            font-weight: 700;
            padding: 3px 8px;
            border-radius: 4px;
        }}

        /* カード */
        .card {{
            background: #1a1a1a;
            border: 1px solid #2a2a2a;
            border-radius: 12px;
            padding: 18px;
            margin-bottom: 14px;
            transition: border-color 0.2s;
        }}
        .card:hover {{ border-color: #444; }}

        .card-header {{
            display: flex;
            align-items: center;
            flex-wrap: wrap;
            gap: 8px;
            margin-bottom: 14px;
        }}

        .badge {{
            font-size: 11px;
            font-weight: 700;
            padding: 3px 10px;
            border-radius: 20px;
        }}
        .badge-reply {{ background: #1e3a5f; color: #60aaff; }}
        .badge-post  {{ background: #1e4f3a; color: #4cdf8a; }}

        .account {{ color: #1d9bf0; font-size: 13px; font-weight: 600; }}
        .score    {{ color: #f4a12a; font-size: 12px; margin-left: auto; }}
        .style-tag {{ color: #888; font-size: 12px; }}
        .time-tag  {{ color: #bbb; font-size: 12px; margin-left: auto; }}
        .char-count {{ color: #555; font-size: 11px; }}

        /* 元の投稿 */
        .original-post {{
            background: #111;
            border-left: 3px solid #333;
            border-radius: 6px;
            padding: 10px 12px;
            margin-bottom: 12px;
        }}
        .label {{
            font-size: 10px;
            color: #555;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 5px;
            font-weight: 600;
        }}
        .original-text {{
            font-size: 13px;
            color: #aaa;
            line-height: 1.5;
        }}

        /* 投稿・返信テキスト */
        .reply-content, .post-content {{
            position: relative;
        }}
        .reply-content .label, .post-content .label {{
            margin-bottom: 8px;
        }}
        .post-text {{
            background: #111;
            border: 1px solid #333;
            border-radius: 8px;
            padding: 14px;
            font-size: 14px;
            line-height: 1.7;
            color: #e8e8e8;
            white-space: pre-wrap;
            word-break: break-word;
            margin-bottom: 10px;
            min-height: 48px;
        }}

        /* 返信アクション行 */
        .reply-actions {{
            display: flex;
            gap: 8px;
            align-items: stretch;
        }}
        .reply-actions .copy-btn {{ flex: 1; }}
        .open-tweet-btn {{
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 8px 16px;
            background: #1e3a5f;
            color: #60aaff;
            border-radius: 6px;
            font-size: 13px;
            font-weight: 600;
            text-decoration: none;
            white-space: nowrap;
            transition: background 0.15s;
        }}
        .open-tweet-btn:hover {{ background: #1d4a7a; }}

        /* コピーボタン */
        .copy-btn {{
            background: #1d9bf0;
            color: #fff;
            border: none;
            border-radius: 6px;
            padding: 8px 18px;
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.15s, transform 0.1s;
            width: 100%;
        }}
        .copy-btn:hover {{ background: #1a8cd8; }}
        .copy-btn:active {{ transform: scale(0.98); }}
        .copy-btn.copied {{
            background: #27ae60;
        }}

        /* ヒントボックス */
        .tips-box {{
            background: #161f2c;
            border: 1px solid #1d3a5a;
            border-radius: 12px;
            padding: 18px;
            margin-top: 32px;
        }}
        .tips-box h3 {{
            color: #1d9bf0;
            font-size: 14px;
            margin-bottom: 12px;
        }}
        .tip-item {{
            display: flex;
            gap: 10px;
            margin-bottom: 10px;
            font-size: 13px;
            line-height: 1.5;
            color: #ccc;
        }}
        .tip-item .tip-icon {{ flex-shrink: 0; }}

        /* 投稿結果バッジ */
        .posted-badge {{
            color: #4cdf8a;
            font-size: 12px;
            font-weight: 600;
            text-decoration: none;
            margin-left: auto;
        }}
        .posted-badge:hover {{ text-decoration: underline; }}
        .dry-badge   {{ color: #60aaff; font-size: 12px; margin-left: auto; }}
        .error-badge {{ color: #f55; font-size: 12px; margin-left: auto; }}
        .manual-badge {{ color: #888; font-size: 12px; margin-left: auto; }}

        /* フッター */
        .footer {{
            text-align: center;
            color: #444;
            font-size: 12px;
            margin-top: 32px;
            padding-bottom: 16px;
        }}

        /* 時間割 */
        .schedule {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 10px;
            margin-bottom: 24px;
        }}
        .schedule-item {{
            background: #1a1a1a;
            border: 1px solid #2a2a2a;
            border-radius: 10px;
            padding: 14px;
            text-align: center;
        }}
        .schedule-item .stime {{
            font-size: 18px;
            font-weight: 700;
            color: #1d9bf0;
            margin-bottom: 4px;
        }}
        .schedule-item .slabel {{
            font-size: 11px;
            color: #888;
        }}
    </style>
</head>
<body>
<div class="container">

    <!-- ヘッダー -->
    <div class="header">
        <h1>🚀 AI X Bot アクションプラン</h1>
        <div class="date">{date_str}（{time_str}生成）</div>
        <div class="tagline">今日やることをすべてここにまとめました</div>
    </div>

    <!-- 時間割 -->
    <div class="schedule">
        <div class="schedule-item">
            <div class="stime">7:00</div>
            <div class="slabel">返信タイム<br>（最優先）</div>
        </div>
        <div class="schedule-item">
            <div class="stime">12:00</div>
            <div class="slabel">投稿②<br>昼休みに拡散</div>
        </div>
        <div class="schedule-item">
            <div class="stime">21:00</div>
            <div class="slabel">投稿③<br>夜の活動時間帯</div>
        </div>
    </div>

    <!-- STEP 1: 返信 -->
    <div class="section-title">
        <span class="step">STEP 1</span>
        大手アカウントへの返信（フォロワー獲得の近道）
    </div>
    {reply_cards}

    <!-- STEP 2: オリジナル投稿 -->
    <div class="section-title">
        <span class="step">STEP 2</span>
        本日のオリジナル投稿
    </div>
    {post_cards}

    <!-- 今日のヒント -->
    <div class="tips-box">
        <h3>💡 フォロワー0→500の鉄則</h3>
        <div class="tip-item">
            <span class="tip-icon">1️⃣</span>
            <span><strong>手動返信で先手を打つ</strong>：上の返信文を「コピー」→「🐦 ツイートを開く」→貼り付けて送信。アカウントが育つと自動返信も有効になります。</span>
        </div>
        <div class="tip-item">
            <span class="tip-icon">2️⃣</span>
            <span><strong>投稿後30分が勝負</strong>：投稿したらすぐ他のAI投稿を5件いいね → アルゴリズムに乗りやすくなる。</span>
        </div>
        <div class="tip-item">
            <span class="tip-icon">3️⃣</span>
            <span><strong>毎日 main.py --scrape を実行</strong>：最新トレンドの収集・投稿・レポート生成をすべて自動化。</span>
        </div>
    </div>

    <div class="footer">AI X Bot — {date_str} 生成</div>
</div>

<script>
function copyText(id, btn) {{
    const el = document.getElementById(id);
    // innerTextで改行もコピー
    const text = el.innerText;
    navigator.clipboard.writeText(text).then(() => {{
        btn.textContent = '✅ コピーしました！';
        btn.classList.add('copied');
        setTimeout(() => {{
            btn.textContent = '📋 コピー';
            btn.classList.remove('copied');
        }}, 2000);
    }});
}}
</script>
</body>
</html>"""

    # HTMLファイルを保存
    output_dir = Path(__file__).parent / "reports"
    output_dir.mkdir(exist_ok=True)
    report_path = output_dir / f"plan_{now.strftime('%Y%m%d_%H%M')}.html"

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"  🌐 レポート生成: {report_path}")

    # ブラウザで自動的に開く
    webbrowser.open(f"file:///{report_path.as_posix()}")
    print("  ✅ ブラウザで開きました")

    return str(report_path)
