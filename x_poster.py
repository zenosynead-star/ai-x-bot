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

    REPLY_MODE 環境変数で送信方法を切り替え:
      - "auto"   (推奨): まずリプライを試行 → 403 ならメンション投稿にフォールバック。
                         X 側の制限が解除されたら自動的に本来のリプライに移行する。
      - "reply"        : in_reply_to_tweet_id 指定のリプライのみ。
                         新規アカウントは 403 で弾かれる。
      - "mention"      : 本文先頭に @username を付けた通常投稿のみ。
                         403 を確実に回避するが、相手のリプライ欄には出ない。

    Returns:
        各投稿の結果リスト（"mode" キーで実際の送信方法を記録）
    """
    reply_mode = os.getenv("REPLY_MODE", "reply").lower()
    results = []
    total = len(replies)
    success_count = 0

    print(f"\n📤 返信を自動投稿します（{total}件、REPLY_MODE={reply_mode}）")

    for i, r in enumerate(replies, 1):
        tweet_id = r.get("tweet_id")
        account = r.get("original_account") or ""
        result = None
        actual_mode = None

        if reply_mode == "auto":
            # まず本来のリプライを試行
            print(f"\n  [{i}/{total}] {account} へリプライ試行 (auto)")
            result = post_tweet(r["reply"], reply_to_id=tweet_id)
            actual_mode = "reply"

            # 403 (REPLY_RESTRICTED) ならメンション投稿で再送
            if result.get("message") == "REPLY_RESTRICTED":
                print(f"  ⚠️  リプライ制限 → メンション投稿でフォールバック")
                fallback_text = f"{account} {r['reply']}".strip()
                result = post_tweet(fallback_text, reply_to_id=None)
                actual_mode = "mention_fallback"

        elif reply_mode == "mention":
            print(f"\n  [{i}/{total}] {account} へメンション投稿")
            text = f"{account} {r['reply']}".strip()
            result = post_tweet(text, reply_to_id=None)
            actual_mode = "mention"

        else:  # "reply" (default)
            print(f"\n  [{i}/{total}] {account} へリプライ")
            result = post_tweet(r["reply"], reply_to_id=tweet_id)
            actual_mode = "reply"
            if result.get("message") == "REPLY_RESTRICTED":
                print(f"  ⚠️  リプライ制限 → スキップ")
                result["message"] = "返信制限のためスキップ"

        result["original_account"] = account
        result["mode"] = actual_mode
        results.append(result)
        if result["success"]:
            success_count += 1

        if i < total and not is_dry_run():
            print(f"  ⏳ {interval}秒待機中...")
            time.sleep(interval)

    # auto モードの場合、reply 成功とfallback 成功を区別して表示
    reply_ok = sum(1 for r in results if r.get("mode") == "reply" and r.get("success"))
    mention_ok = sum(1 for r in results if r.get("mode") in ("mention", "mention_fallback") and r.get("success"))
    print(f"\n  ✅ 返信完了: {success_count}/{total}件 成功 (リプライ {reply_ok}件 + メンション {mention_ok}件)")
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
