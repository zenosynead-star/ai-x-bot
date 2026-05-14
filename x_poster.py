"""
X（Twitter）投稿モジュール
生成した投稿文・返信をXに自動投稿する
"""

import os
import time
import tweepy
from datetime import datetime


def get_x_client():
    """X API v2 クライアントを返す"""
    client = tweepy.Client(
        bearer_token=os.getenv("X_BEARER_TOKEN"),
        consumer_key=os.getenv("X_API_KEY"),
        consumer_secret=os.getenv("X_API_SECRET"),
        access_token=os.getenv("X_ACCESS_TOKEN"),
        access_token_secret=os.getenv("X_ACCESS_TOKEN_SECRET"),
        wait_on_rate_limit=True,
    )
    return client


def is_dry_run() -> bool:
    return os.getenv("DRY_RUN", "True").lower() in ("true", "1", "yes")


def post_tweet(text: str, reply_to_id: str = None) -> dict:
    """
    Xに投稿（または返信）する

    Args:
        text: 投稿テキスト
        reply_to_id: 返信先ツイートID（Noneなら通常投稿）

    Returns:
        {"success": bool, "tweet_id": str, "url": str, "message": str}
    """
    dry_run = is_dry_run()
    label = "返信" if reply_to_id else "投稿"
    timestamp = datetime.now().strftime("%H:%M:%S")

    print(f"\n  [{timestamp}] {label}{'（DRY RUN）' if dry_run else ''}:")
    print(f"  {'─'*50}")
    for line in text.splitlines():
        print(f"  {line}")
    print(f"  {'─'*50}")
    print(f"  文字数: {len(text)}/280")

    if dry_run:
        print("  ⚠️  DRY RUN — 実際には送信されていません")
        return {"success": True, "tweet_id": None, "url": None, "message": "DRY_RUN"}

    try:
        client = get_x_client()
        kwargs = {"text": text}
        if reply_to_id:
            kwargs["in_reply_to_tweet_id"] = reply_to_id

        response = client.create_tweet(**kwargs)
        tweet_id = response.data["id"]
        url = f"https://x.com/i/web/status/{tweet_id}"
        print(f"  ✅ 成功！ → {url}")
        return {"success": True, "tweet_id": tweet_id, "url": url, "message": "OK"}

    except tweepy.TooManyRequests:
        msg = "❌ レート制限。少し待ってから再実行してください。"
        print(f"  {msg}")
        return {"success": False, "tweet_id": None, "url": None, "message": msg}

    except tweepy.Forbidden as e:
        err_str = str(e)
        if "not allowed" in err_str or "not permitted" in err_str:
            msg = "REPLY_RESTRICTED"   # 返信制限ツイート（呼び元でリトライ）
        else:
            msg = f"❌ 権限エラー: {e}"
            print(f"  {msg}")
        return {"success": False, "tweet_id": None, "url": None, "message": msg}

    except Exception as e:
        msg = f"❌ エラー: {e}"
        print(f"  {msg}")
        return {"success": False, "tweet_id": None, "url": None, "message": msg}


def post_replies(replies: list, interval: int = 45) -> list:
    """
    返信リストを順番に投稿する。

    REPLY_MODE 環境変数で送信方法を切り替え可能:
      - "reply"   (default): in_reply_to_tweet_id を指定したリプライとして送る
                             ※新規アカウントは X が 403 で弾く
      - "mention":           本文先頭に @username を付けた通常投稿として送る
                             ※相手のメンション欄に通知。403を回避できる

    Args:
        replies: generate_replies_for_trends() の出力リスト
        interval: 投稿間隔（秒）

    Returns:
        各投稿の結果リスト
    """
    reply_mode = os.getenv("REPLY_MODE", "reply").lower()
    results = []
    total = len(replies)
    success_count = 0

    label = "メンション投稿" if reply_mode == "mention" else "返信"
    print(f"\n📤 {label}を自動投稿します（{total}件、mode={reply_mode}）")

    for i, r in enumerate(replies, 1):
        tweet_id = r.get("tweet_id")
        account = r.get("original_account") or ""
        print(f"\n  [{i}/{total}] {account} への{label}")

        if reply_mode == "mention":
            # メンション投稿: @username を本文先頭に付けて通常投稿として送る
            text = f"{account} {r['reply']}".strip()
            result = post_tweet(text, reply_to_id=None)
        else:
            result = post_tweet(r["reply"], reply_to_id=tweet_id)

        # 返信制限エラー → スキップして記録
        if result.get("message") == "REPLY_RESTRICTED":
            print(f"  ⚠️  このツイートは返信制限あり → スキップ")
            result["message"] = "返信制限のためスキップ"
            result["original_account"] = account
            results.append(result)
            continue

        result["original_account"] = account
        result["mode"] = reply_mode
        results.append(result)
        if result["success"]:
            success_count += 1

        if i < total and not is_dry_run():
            print(f"  ⏳ {interval}秒待機中...")
            time.sleep(interval)

    print(f"\n  ✅ {label}完了: {success_count}/{total}件 成功")
    return results


def post_original_posts(posts: list, interval: int = 120) -> list:
    """
    オリジナル投稿リストを順番に投稿する

    Args:
        posts: generate_daily_posts() の出力リスト
        interval: 投稿間隔（秒）
    """
    results = []
    total = len(posts)

    print(f"\n📤 オリジナル投稿を自動投稿します（{total}件）")

    for i, item in enumerate(posts, 1):
        style_label = {"breaking": "速報", "tips": "Tips", "alert": "警告", "story": "共感"}.get(item["style"], item["style"])
        print(f"\n  [{i}/{total}] {style_label}型 ({item['char_count']}文字)")

        result = post_tweet(item["post"])
        result["style"] = item["style"]
        results.append(result)

        if i < total and not is_dry_run():
            print(f"  ⏳ {interval}秒待機中...")
            time.sleep(interval)

    ok = sum(1 for r in results if r["success"])
    print(f"\n  ✅ 投稿完了: {ok}/{total}件 成功")
    return results
