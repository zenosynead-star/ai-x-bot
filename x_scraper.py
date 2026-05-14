"""
X トレンド収集モジュール（X API v2版）
Playwright不要 — tweepyのBearerトークンで直接取得する
"""

import os
import re
import json
import time
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# 監視する人気AIアカウント（フォロワー順）
TARGET_ACCOUNTS = [
    "masahirochaen",   # 19.2万F
    "ctgptlb",         # 13.7万F
    "chatgptair",      # 10.8万F
    "SuguruKun_ai",    # 10.5万F
    "hashimoto_no14",  # 3.9万F
]

TRENDS_FILE  = "today_trends.json"
MAX_PER_ACCT = 3   # アカウントごとの最大取得件数


# ────────────────────────────────────────
# X API v2 クライアント
# ────────────────────────────────────────

def _get_client():
    import tweepy
    return tweepy.Client(
        bearer_token=os.getenv("X_BEARER_TOKEN"),
        consumer_key=os.getenv("X_API_KEY"),
        consumer_secret=os.getenv("X_API_SECRET"),
        access_token=os.getenv("X_ACCESS_TOKEN"),
        access_token_secret=os.getenv("X_ACCESS_TOKEN_SECRET"),
        wait_on_rate_limit=True,
    )


# ────────────────────────────────────────
# ユーザーIDキャッシュ（API節約）
# ────────────────────────────────────────

_uid_cache: dict[str, str] = {}


def _get_user_id(client, handle: str) -> str | None:
    if handle in _uid_cache:
        return _uid_cache[handle]
    try:
        resp = client.get_user(username=handle)
        if resp.data:
            _uid_cache[handle] = str(resp.data.id)
            return _uid_cache[handle]
    except Exception as e:
        print(f"  ⚠️  @{handle} ID取得失敗: {e}")
    return None


# ────────────────────────────────────────
# 1アカウントのツイートを取得
# ────────────────────────────────────────

def _fetch_posts_for_account(client, handle: str, max_posts: int = MAX_PER_ACCT) -> list:
    uid = _get_user_id(client, handle)
    if not uid:
        return []

    try:
        resp = client.get_users_tweets(
            id=uid,
            max_results=min(max_posts * 5, 20),   # フィルタ後にmax_postsになるよう多めに取る
            tweet_fields=["public_metrics", "created_at", "reply_settings"],
            exclude=["retweets", "replies"],       # RTと返信を除外
        )
    except Exception as e:
        print(f"  ⚠️  @{handle} ツイート取得失敗: {e}")
        return []

    if not resp.data:
        return []

    posts = []
    for tweet in resp.data:
        if len(posts) >= max_posts:
            break

        text = tweet.text

        # 短すぎる投稿はスキップ
        if len(text) < 15:
            continue
        # URLを除いた本文が30文字未満ならスキップ（URLだけの宣伝投稿を除外）
        text_no_url = re.sub(r"https?://\S+", "", text).strip()
        if len(text_no_url) < 30:
            continue

        # 返信制限あり（everyoneでない）はスキップ
        reply_settings = getattr(tweet, "reply_settings", None)
        if reply_settings and reply_settings != "everyone":
            continue

        m = tweet.public_metrics
        likes      = m.get("like_count",    0)
        retweets   = m.get("retweet_count", 0)
        replies_ct = m.get("reply_count",   0)

        tweet_id  = str(tweet.id)
        tweet_url = f"https://x.com/{handle}/status/{tweet_id}"

        posts.append({
            "account":          f"@{handle}",
            "text":             text[:280],
            "tweet_id":         tweet_id,
            "tweet_url":        tweet_url,
            "likes":            likes,
            "retweets":         retweets,
            "replies":          replies_ct,
            "engagement_score": likes + retweets * 3 + replies_ct * 2,
        })

    return posts


# ────────────────────────────────────────
# メイン: 全アカウントから収集
# ────────────────────────────────────────

def collect_trending_posts() -> list:
    """全ターゲットアカウントから今日のバズり投稿を収集する。"""
    print("🌐 X API v2 でトレンドを収集中...")

    try:
        client = _get_client()
        all_posts: list = []

        for handle in TARGET_ACCOUNTS:
            print(f"  📋 @{handle} を収集中...")
            posts = _fetch_posts_for_account(client, handle, max_posts=MAX_PER_ACCT)
            all_posts.extend(posts)
            label = f"{len(posts)}件"
            if posts:
                label += f"（うちID付き: {sum(1 for p in posts if p.get('tweet_id'))}件）"
            print(f"     → {label}")
            time.sleep(0.5)   # API節約

        if not all_posts:
            print("  ⚠️  投稿が0件 → フォールバックデータを使用します")
            return load_fallback_trends()

        print(f"  ✅ API収集成功: 合計 {len(all_posts)} 件")

        # エンゲージメント降順にソート
        all_posts.sort(key=lambda x: x["engagement_score"], reverse=True)

        save_trends(all_posts)
        return all_posts

    except Exception as e:
        print(f"  ⚠️  API収集エラー: {e}")
        print("  → フォールバック: 保存済みトレンドデータを使用します")
        return load_fallback_trends()


# ────────────────────────────────────────
# 保存 / 読み込み
# ────────────────────────────────────────

def save_trends(posts: list):
    """トレンドデータをJSONに保存"""
    data = {
        "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "posts":        posts,
    }
    with open(TRENDS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  💾 {len(posts)}件のトレンドを保存しました")


def load_trends() -> list:
    """保存済みトレンドを読み込む"""
    if not Path(TRENDS_FILE).exists():
        return load_fallback_trends()

    with open(TRENDS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    collected  = datetime.strptime(data["collected_at"], "%Y-%m-%d %H:%M")
    hours_ago  = (datetime.now() - collected).total_seconds() / 3600
    if hours_ago > 24:
        print("  ⚠️  トレンドデータが古いです（24時間超）。再収集を推奨します。")

    return data["posts"]


def load_fallback_trends() -> list:
    """フォールバック用: 分析済みバズり投稿パターン"""
    return [
        {
            "account": "@ctgptlb",
            "text": "【速報】OpenAI、約6,000億円規模のAI導入会社を設立\n\nTPG、Bain、McKinseyなど19社が参加。AI専門人材150名を初日から投入。\n\n続報はフォローで見逃さずに🙏",
            "tweet_id": None, "tweet_url": None,
            "likes": 2250, "retweets": 280, "replies": 60,
            "engagement_score": 3150,
        },
        {
            "account": "@masahirochaen",
            "text": "【保存版】Claude Code Desktopアプリ完全解説マニュアル\n\nDesktopアプリが便利すぎて普段の研修でも推しています。\n\n非エンジニアの方はターミナルよりも圧倒的に始めやすい。",
            "tweet_id": None, "tweet_url": None,
            "likes": 950, "retweets": 96, "replies": 8,
            "engagement_score": 1254,
        },
        {
            "account": "@chatgptair",
            "text": "ChatGPTで仕事が10倍速くなる使い方5選\n\n①議事録→要約：30秒\n②メール返信：一発生成\n③資料作成：構成から出力\n④アイデア：100案を3分\n⑤エラー解決：即特定\n\n保存して使ってね👇",
            "tweet_id": None, "tweet_url": None,
            "likes": 1800, "retweets": 210, "replies": 45,
            "engagement_score": 2520,
        },
    ]


# ────────────────────────────────────────
# 単体テスト
# ────────────────────────────────────────

if __name__ == "__main__":
    import sys, io
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    posts = collect_trending_posts()
    print(f"\n収集完了: {len(posts)}件")
    for p in posts[:5]:
        print(f"\n{p['account']} (スコア:{p['engagement_score']}, ID:{p['tweet_id']})")
        print(p["text"][:100])
