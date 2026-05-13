"""ハッシュタグ検索でAI系ツイートを収集し、返信テストを行う"""
import time, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from dotenv import load_dotenv
load_dotenv()
from playwright.sync_api import sync_playwright
from reply_generator import generate_reply
from x_poster import post_tweet

SEARCH_QUERIES = ["#生成AI", "#ChatGPT活用", "#AI仕事術"]

def search_replyable_tweets(page, query, max_results=5):
    """ハッシュタグ検索で返信制限のないAIツイートを取得"""
    import urllib.parse
    encoded = urllib.parse.quote(query)
    url = f"https://x.com/search?q={encoded}&f=live"  # 最新順
    page.goto(url, wait_until="domcontentloaded", timeout=15000)
    time.sleep(4)

    results = []
    articles = page.query_selector_all("article[data-testid='tweet']")
    print(f"  '{query}' → {len(articles)}件の記事を発見")

    for art in articles[:15]:
        if len(results) >= max_results:
            break
        try:
            # テキスト取得
            text_el = art.query_selector("[data-testid='tweetText']")
            if not text_el:
                continue
            text = text_el.inner_text()
            if len(text) < 15 or "https://" in text:
                continue

            # 返信制限チェック
            btn = art.query_selector("[data-testid='reply']")
            if btn and btn.get_attribute("aria-disabled") == "true":
                continue

            # アカウント名
            user_el = art.query_selector("[data-testid='User-Name']")
            account = user_el.inner_text().split("\n")[0] if user_el else "unknown"

            # ツイートID（/status/ を含むリンクから）
            links = art.query_selector_all("a[href*='/status/']")
            tid = None
            handle = None
            for link in links:
                href = link.get_attribute("href") or ""
                if "/status/" in href and not "/photo/" in href:
                    parts = href.split("/status/")
                    if len(parts) > 1:
                        tid = parts[-1].split("?")[0].split("/")[0]
                        handle = href.split("/status/")[0].lstrip("/")
                        break

            if not tid:
                continue

            results.append({
                "account": f"@{handle}" if handle else account,
                "text": text[:280],
                "tweet_id": tid,
                "tweet_url": f"https://x.com/{handle}/status/{tid}" if handle else None,
                "engagement_score": 0,
            })
            print(f"    ✅ @{handle}: {text[:40]}...")
        except Exception:
            continue

    return results

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
    )
    ctx = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    page = ctx.new_page()

    all_tweets = []
    for q in SEARCH_QUERIES:
        tweets = search_replyable_tweets(page, q, max_results=3)
        all_tweets.extend(tweets)
        if len(all_tweets) >= 3:
            break
        time.sleep(2)

    browser.close()

print(f"\n合計 {len(all_tweets)} 件取得")

if not all_tweets:
    print("ツイートが取得できませんでした")
    sys.exit(1)

# 1件だけ返信テスト
post = all_tweets[0]
print(f"\n--- 返信テスト ---")
print(f"返信先: {post['account']}")
print(f"tweet_id: {post['tweet_id']}")
print(f"元投稿: {post['text'][:60]}")

reply_text = generate_reply(post)
print(f"\n生成した返信文: {reply_text}")

result = post_tweet(reply_text, reply_to_id=post["tweet_id"])
print(f"\n結果: {result}")
