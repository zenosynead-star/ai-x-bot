"""
AI X Bot — フォロワー成長特化版
毎日実行するだけで返信・投稿を自動化する
"""

import os, sys, io, json, schedule, time
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

from news_fetcher import get_top_news
from post_generator import generate_daily_posts
from reply_generator import generate_replies_for_trends
from x_scraper import collect_trending_posts, load_trends
from x_analyzer import BUZZ_PATTERNS
from report_generator import generate_report
from x_poster import post_replies, post_original_posts, is_dry_run

load_dotenv()
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

MAX_POSTS = int(os.getenv("MAX_POSTS_PER_DAY", "3"))
MAX_REPLIES = int(os.getenv("MAX_REPLIES_PER_DAY", "5"))


def save_history(reply_results, replies, post_results, original_posts):
    """実行履歴を history/YYYYMMDD_HHMMSS.json として保存。
    Streamlit 管理画面が artifact 経由でこの JSON を読んで履歴表示に使う。
    """
    Path("history").mkdir(exist_ok=True)

    reply_history = []
    for i, r in enumerate(reply_results):
        rp = replies[i] if i < len(replies) else {}
        reply_history.append({
            "original_account": r.get("original_account") or rp.get("original_account"),
            "reply_text":       rp.get("reply", ""),
            "tweet_id":         rp.get("tweet_id"),
            "tweet_url":        rp.get("tweet_url"),
            "success":          r.get("success"),
            "message":          r.get("message"),
            "url":              r.get("url"),
        })

    post_history = []
    for i, r in enumerate(post_results):
        op = original_posts[i] if i < len(original_posts) else {}
        post_history.append({
            "style":         op.get("style") or r.get("style"),
            "post_text":     op.get("post", ""),
            "char_count":    op.get("char_count"),
            "twitter_count": op.get("twitter_count"),
            "news_title":    (op.get("news") or {}).get("title"),
            "success":       r.get("success"),
            "message":       r.get("message"),
            "url":           r.get("url"),
        })

    entry = {
        "timestamp": datetime.now().isoformat(),
        "dry_run":   is_dry_run(),
        "replies":   reply_history,
        "posts":     post_history,
    }

    fname = Path("history") / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    fname.write_text(json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  💾 履歴を保存: {fname}")


def print_header():
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    mode = "DRY RUN（テスト）" if is_dry_run() else "🔴 本番投稿モード"
    print(f"""
{'='*62}
🚀  AI Xアカウント 成長ツール  [{now}]  {mode}
{'='*62}""")


def run_bot(scrape_fresh: bool = True):
    print_header()

    # ===== Step 1: トレンド収集 =====
    print("\n【STEP 1】 今日のXトレンドを収集")
    print("─" * 40)
    if scrape_fresh:
        trending_posts = collect_trending_posts()
    else:
        print("  📂 保存済みトレンドを使用")
        trending_posts = load_trends()
    print(f"  ✅ {len(trending_posts)}件のバズり投稿を収集\n")

    # ===== Step 2: 返信文生成 =====
    print("【STEP 2】 大手アカウントへの返信文を生成")
    print("─" * 40)
    replies = generate_replies_for_trends(trending_posts, count=MAX_REPLIES)

    # ===== Step 3: オリジナル投稿生成 =====
    print(f"\n【STEP 3】 本日のオリジナル投稿を生成")
    print("─" * 40)
    news_items = get_top_news(n=MAX_POSTS + 2)
    original_posts = generate_daily_posts(news_items, count=MAX_POSTS)

    # ===== Step 4: 自動投稿 =====
    print(f"\n【STEP 4】 Xへ自動投稿")
    print("─" * 40)

    reply_results = post_replies(replies, interval=45)

    # 返信→投稿の間にクールダウン（X APIの連続投稿制限を避ける）
    if not is_dry_run() and replies:
        cooldown = 120
        print(f"\n  ⏳ クールダウン中（{cooldown}秒）...")
        time.sleep(cooldown)

    post_results = post_original_posts(original_posts, interval=120)

    # ===== Step 5: HTMLレポート =====
    print("\n\n【STEP 5】 レポート生成")
    print("─" * 40)
    best_times = BUZZ_PATTERNS["best_post_times"]
    generate_report(replies, original_posts, best_times,
                    reply_results=reply_results, post_results=post_results)

    # ===== Step 6: 履歴を JSON 保存（管理画面が参照） =====
    save_history(reply_results, replies, post_results, original_posts)

    # サマリー表示
    ok_replies = sum(1 for r in reply_results if r["success"])
    ok_posts   = sum(1 for r in post_results  if r["success"])
    total = ok_replies + ok_posts
    cost_usd = total * 0.015

    if is_dry_run():
        print(f"""
{'='*62}
✅ DRY RUN完了（実際には投稿されていません）
   本番投稿するには .env の DRY_RUN=False に変更してください。
{'='*62}
""")
    else:
        print(f"""
{'='*62}
✅ 本日の自動投稿完了！
   返信: {ok_replies}/{len(reply_results)}件  投稿: {ok_posts}/{len(original_posts)}件
   消費コスト: 約 ${cost_usd:.3f}（約{cost_usd*150:.0f}円）
   ブラウザで投稿URLを確認してください。
{'='*62}
""")


def start_scheduler():
    """スケジューラーモード（引数なし起動時）"""
    print_header()
    post_times_raw = os.getenv("POST_TIMES", "07:00,12:00,21:00").split(",")
    post_times = [t.strip() for t in post_times_raw]

    print("⏰ スケジューラーモード起動")
    print(f"   朝 {post_times[0]} に収集・返信・投稿1を実行")
    for t in post_times[1:]:
        print(f"   {t} に追加投稿を実行")

    # 朝の実行：スクレイプ＋全自動
    schedule.every().day.at(post_times[0]).do(lambda: run_bot(scrape_fresh=True))

    # それ以外の時間：保存済みデータで投稿のみ（実装簡略化）
    for t in post_times[1:]:
        schedule.every().day.at(t).do(lambda: run_bot(scrape_fresh=False))

    print("\n待機中... (Ctrl+C で停止)\n")
    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    args = sys.argv[1:]

    if "--scrape" in args:
        run_bot(scrape_fresh=True)
    elif "--now" in args:
        run_bot(scrape_fresh=False)
    elif "--report" in args:
        # 投稿せずレポートのみ再生成
        print_header()
        print("\n📊 レポートのみ再生成します（投稿なし）\n")
        trends = load_trends()
        from reply_generator import generate_replies_for_trends
        replies = generate_replies_for_trends(trends, count=MAX_REPLIES)
        from post_generator import generate_daily_posts
        from news_fetcher import get_top_news
        news = get_top_news(n=MAX_POSTS + 2)
        from post_generator import generate_daily_posts
        posts = generate_daily_posts(news, count=MAX_POSTS)
        from x_analyzer import BUZZ_PATTERNS
        generate_report(replies, posts, BUZZ_PATTERNS["best_post_times"])
    elif "--test-reply" in args:
        # 自動返信のテスト（403解除確認用）。`--test-reply 5` のように件数指定可能
        idx = args.index("--test-reply")
        test_count = int(args[idx+1]) if idx + 1 < len(args) and args[idx+1].isdigit() else 3
        print_header()
        print(f"\n🧪 自動返信テスト（{test_count}件・本番投稿）\n")
        trends = load_trends()
        if not trends:
            print("❌ today_trends.json が空。先に --scrape を実行してください")
            sys.exit(1)
        replies = generate_replies_for_trends(trends, count=test_count)
        if not replies:
            print("❌ 返信文を生成できませんでした")
            sys.exit(1)
        results = post_replies(replies, interval=30)
        ok = sum(1 for r in results if r["success"])
        restricted = sum(1 for r in results if "返信制限" in r.get("message", ""))
        print(f"\n結果: 成功 {ok}/{len(results)}件、返信制限 {restricted}件")
        if ok > 0:
            print("✅ アカウント制限は解除されています")
        elif restricted == len(results):
            print("⛔ 全件返信制限 → アカウント全体の制限が継続中の可能性大")
    else:
        start_scheduler()
