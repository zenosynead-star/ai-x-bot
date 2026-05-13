"""
候補アカウントの返信制限チェックスクリプト
返信ボタンの aria-disabled 状態を確認する
"""
import time
from playwright.sync_api import sync_playwright

# テスト候補（中規模3000〜3万F想定）
CANDIDATES = [
    "pop_ikeda",       # 3.4万F（x_analyzerに掲載）
    "gpt_jp",          # GPT JP
    "ChatgptAIskill",  # AIスキルアカデミー
    "usutaku_com",     # AIクリエイター
    "mocchicc",        # AIユーザー
    "goto_yuta_",      # データサイエンティスト
    "zikilluu",        # AI系
    "ai_database",     # AIデータベース
]


def check_account(page, handle):
    try:
        page.goto(f"https://x.com/{handle}", wait_until="domcontentloaded", timeout=12000)
        time.sleep(2)
        articles = page.query_selector_all("article[data-testid='tweet']")
        results = []
        for art in articles[:6]:
            text_el = art.query_selector("[data-testid='tweetText']")
            if not text_el:
                continue
            text = text_el.inner_text()
            if len(text) < 10:
                continue
            if "https://" in text:
                continue
            inner = art.inner_text()
            if "ピン留め" in inner or "Pinned" in inner:
                continue

            # reply ボタンの disabled 状態確認
            btn = art.query_selector("[data-testid='reply']")
            disabled = None
            if btn:
                disabled = btn.get_attribute("aria-disabled") == "true"

            # tweet ID 取得
            link = art.query_selector(f"a[href*='/{handle}/status/']")
            tid = None
            if link:
                href = link.get_attribute("href") or ""
                parts = href.split("/status/")
                if len(parts) > 1:
                    tid = parts[-1].split("?")[0]

            results.append({
                "text": text[:40],
                "disabled": disabled,
                "tweet_id": tid,
            })
        return results
    except Exception as e:
        return [{"error": str(e)[:60]}]


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

    print(f"{'アカウント':<22} {'取得':<5} {'返信OK':<7} btn_disabled状況")
    print("-" * 65)

    for handle in CANDIDATES:
        res = check_account(page, handle)
        if res and "error" in res[0]:
            print(f"@{handle:<20} ERROR: {res[0]['error']}")
            continue
        ok = [r for r in res if r.get("tweet_id") and r.get("disabled") is False]
        disabled_vals = [r.get("disabled") for r in res[:3]]
        print(f"@{handle:<20} {len(res):<5} {len(ok):<7} {disabled_vals}")

    browser.close()
