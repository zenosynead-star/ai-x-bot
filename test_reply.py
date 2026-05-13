"""1件だけ返信テスト"""
import time, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from dotenv import load_dotenv
load_dotenv()

from playwright.sync_api import sync_playwright
from reply_generator import generate_reply
from x_poster import post_tweet

HANDLE = "ChatgptAIskill"  # 返信ボタン有効だったアカウント

def get_first_tweet(handle):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        page = ctx.new_page()
        page.goto(f"https://x.com/{handle}", wait_until="domcontentloaded", timeout=12000)
        time.sleep(2)
        articles = page.query_selector_all("article[data-testid='tweet']")
        for art in articles[:5]:
            text_el = art.query_selector("[data-testid='tweetText']")
            if not text_el: continue
            text = text_el.inner_text()
            if len(text) < 10 or "https://" in text: continue
            if "ピン留め" in art.inner_text(): continue
            link = art.query_selector(f"a[href*='/{handle}/status/']")
            if not link: continue
            href = link.get_attribute("href") or ""
            parts = href.split("/status/")
            if len(parts) < 2: continue
            tid = parts[-1].split("?")[0]
            browser.close()
            return {"account": f"@{handle}", "text": text, "tweet_id": tid,
                    "tweet_url": f"https://x.com/{handle}/status/{tid}"}
        browser.close()
    return None

post = get_first_tweet(HANDLE)
if not post:
    print("ツイート取得失敗")
    sys.exit(1)

print("返信先:", post["account"])
print("tweet_id:", post["tweet_id"])
print("元投稿:", post["text"][:60])
print()

reply_text = generate_reply(post)
print("生成した返信文:")
print(reply_text)
print()

result = post_tweet(reply_text, reply_to_id=post["tweet_id"])
print("\n結果:", result)
