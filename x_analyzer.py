"""
X トレンド分析モジュール
伸びているAIアカウントの投稿パターンを分析する
"""

# 調査済みの人気アカウント（フォロワー数順）
TOP_AI_ACCOUNTS = [
    {"handle": "masahirochaen", "followers": "19.2万", "style": "重要AIニュースを毎日最速で発信"},
    {"handle": "ctgptlb",       "followers": "13.7万", "style": "【速報】系ニュース＋日本語要約"},
    {"handle": "chatgptair",    "followers": "10.8万", "style": "ChatGPT×AIツール活用法"},
    {"handle": "SuguruKun_ai",  "followers": "10.5万", "style": "生成AIの実践的使い方"},
    {"handle": "hashimoto_no14","followers":  "3.9万", "style": "ChatGPT無料ツール活用"},
    {"handle": "pop_ikeda",     "followers":  "3.4万", "style": "ChatGPT仕事術"},
]

# 分析済みのバズる投稿パターン
BUZZ_PATTERNS = {
    "hooks": [
        "【速報】", "【保存版】", "【永久保存版】", "【必見】",
        "【○選】", "【完全版】", "これは革命的", "知らないと損",
        "乗り遅れないで", "これだけ覚えて", "99%の人が知らない",
    ],
    "structures": [
        "フック → 箇条書き3〜5個 → CTA",
        "フック → ストーリー → 学び → CTA",
        "衝撃の事実 → 理由3つ → 解決策 → CTA",
        "Before/After → 具体的手順 → CTA",
    ],
    "cta_patterns": [
        "続報はフォローで見逃さずに🙏",
        "保存して使ってね👇",
        "フォローで最新AI情報をお届け✨",
        "役に立ったらRT・いいね嬉しいです🙏",
        "フォローして時代に乗り遅れるな🔥",
    ],
    "high_engagement_topics": [
        "ChatGPT/Claude/Geminiの新機能",
        "AIで仕事が○倍速くなる方法",
        "無料で使えるAIツール紹介",
        "AI×副業・収入アップ",
        "AI最新ニュース速報",
        "プロンプトエンジニアリングTips",
        "AIで自動化できる業務",
    ],
    "emoji_patterns": [
        "🚨🤖💡🚀🙏",  # 速報系
        "📚💻✅🎯👇",  # Tips系
        "⚠️🔥💪📈🌊",  # 警告系
    ],
    "best_post_times": ["7:00-8:00", "12:00-13:00", "21:00-22:00"],
}

# 実際にバズった投稿の例（調査で収集）
EXAMPLE_VIRAL_POSTS = [
    {
        "account": "@ctgptlb",
        "impressions": "86万",
        "style": "breaking",
        "text": "【速報】OpenAI、約6,000億円規模のAI導入会社を設立\n\n企業の業務にAIを本格導入する新会社「OpenAI Deployment Company」を発表。\n\nTPG、Bain、McKinsey、Capgemini、SoftBank Corp.など19社が参加。さらにAI導入企業Tomoroを買収し、約150名の専門人材を初日から投入。",
    },
    {
        "account": "@masahirochaen",
        "impressions": "20万",
        "style": "tips",
        "text": "【note公開】Claude Code Desktopアプリ完全解説マニュアル\n\nDesktopアプリが便利すぎて、普段の研修でもかなり推しています。\n\n特に非エンジニアの方は、ターミナルよりもDesktopアプリの方が圧倒的に始めやすいです。",
    },
]


def get_analysis_context() -> dict:
    """
    投稿生成に使う分析コンテキストを返す
    """
    return {
        "top_accounts": TOP_AI_ACCOUNTS,
        "buzz_patterns": BUZZ_PATTERNS,
        "viral_examples": EXAMPLE_VIRAL_POSTS,
    }


def get_todays_strategy() -> str:
    """
    今日の投稿戦略を文字列で返す
    """
    import random
    hook = random.choice(BUZZ_PATTERNS["hooks"])
    structure = random.choice(BUZZ_PATTERNS["structures"])
    cta = random.choice(BUZZ_PATTERNS["cta_patterns"])
    topic = random.choice(BUZZ_PATTERNS["high_engagement_topics"])

    return f"""
今日の投稿戦略：
- 推奨フック: {hook}
- 構成: {structure}
- CTA: {cta}
- 狙うトピック: {topic}
"""
