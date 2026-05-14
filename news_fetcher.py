"""
AI ニュース収集モジュール
RSSフィードから最新のAIニュースを収集する
"""

import feedparser
import requests
from datetime import datetime, timedelta
from typing import List, Dict


# 収集対象のRSSフィード（AI系主要メディア）
RSS_FEEDS = [
    # 英語（海外AI情報）
    {"url": "https://openai.com/news/rss.xml",         "source": "OpenAI"},
    {"url": "https://www.anthropic.com/rss.xml",       "source": "Anthropic"},
    {"url": "https://techcrunch.com/category/artificial-intelligence/feed/", "source": "TechCrunch AI"},
    {"url": "https://venturebeat.com/category/ai/feed/", "source": "VentureBeat AI"},
    {"url": "https://feeds.feedburner.com/blogspot/gJZg", "source": "Google AI Blog"},

    # 日本語（国内AI情報）
    {"url": "https://aismiley.co.jp/feed/",            "source": "AI Smiley"},
    {"url": "https://ainow.ai/feed/",                  "source": "AINOW"},
    {"url": "https://ledge.ai/feed",                   "source": "Ledge.ai"},
]


def fetch_recent_news(hours: int = 24) -> List[Dict]:
    """
    過去N時間以内のAIニュースを収集する

    Args:
        hours: 何時間前まで遡るか（デフォルト24時間）

    Returns:
        ニュース記事のリスト（title, summary, url, source, published）
    """
    cutoff = datetime.now() - timedelta(hours=hours)
    articles = []

    for feed_info in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_info["url"])
            for entry in feed.entries[:5]:  # 各フィードから最大5件
                # 公開日時をパース
                published = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    published = datetime(*entry.published_parsed[:6])

                # 新しい記事のみ取得
                if published and published < cutoff:
                    continue

                summary = ""
                if hasattr(entry, "summary"):
                    # HTMLタグを除去して最初の200文字
                    import re
                    summary = re.sub(r"<[^>]+>", "", entry.summary)[:200]

                articles.append({
                    "title": entry.get("title", ""),
                    "summary": summary,
                    "url": entry.get("link", ""),
                    "source": feed_info["source"],
                    "published": published.strftime("%Y-%m-%d %H:%M") if published else "不明",
                })

        except Exception as e:
            print(f"[フィード取得エラー] {feed_info['source']}: {e}")
            continue

    print(f"[ニュース収集] {len(articles)}件取得")
    return articles


def get_top_news(n: int = 5) -> List[Dict]:
    """
    最新AIニュースをn件返す（重複を除去し重要度でソート）
    """
    articles = fetch_recent_news(hours=48)  # 48時間以内

    # 重複URLを除去
    seen_urls = set()
    unique_articles = []
    for a in articles:
        if a["url"] not in seen_urls:
            seen_urls.add(a["url"])
            unique_articles.append(a)

    # タイトルにAI関連キーワードが含まれる記事を優先
    priority_keywords = [
        "GPT", "Claude", "Gemini", "AI", "LLM", "ChatGPT",
        "OpenAI", "Anthropic", "Google", "Meta", "AGI",
    ]

    def priority_score(article):
        score = 0
        title = article["title"].upper()
        for kw in priority_keywords:
            if kw.upper() in title:
                score += 1
        return score

    unique_articles.sort(key=priority_score, reverse=True)
    return unique_articles[:n]


if __name__ == "__main__":
    import sys
    import io
    try:
        if hasattr(sys.stdout, "buffer"):
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass  # Streamlit Cloud などで stdout を置き換えられない場合は無視

    # テスト実行
    news = get_top_news(3)
    for i, n in enumerate(news, 1):
        print(f"\n--- {i}. {n['source']} ---")
        print(f"タイトル: {n['title']}")
        print(f"要約: {n['summary'][:100]}...")
        print(f"URL: {n['url']}")
