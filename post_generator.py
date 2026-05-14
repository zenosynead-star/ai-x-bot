"""
投稿文生成モジュール（強化版）
Groq API + 分析済みパターンで、バズる投稿を生成する
※ 無料Xアカウント対応: 日本語は2文字換算 → 実質上限 ~130文字
"""

import os
import random
from typing import Dict, Optional
from groq import Groq
from x_analyzer import get_analysis_context, BUZZ_PATTERNS


def twitter_len(text: str) -> int:
    """
    Xの文字数カウント（CJK文字・全角記号は2文字換算）
    無料アカウントの上限は280。日本語のみなら約140文字が実質上限。
    """
    count = 0
    for ch in text:
        cp = ord(ch)
        # CJK文字・ひらがな・カタカナ・全角記号など
        if (0x1100 <= cp <= 0x115F or
            0x2E80 <= cp <= 0x303F or
            0x3040 <= cp <= 0x33FF or
            0xA960 <= cp <= 0xA97F or
            0xAC00 <= cp <= 0xD7FF or
            0xF900 <= cp <= 0xFAFF or
            0xFE10 <= cp <= 0xFE1F or
            0xFE30 <= cp <= 0xFE4F or
            0xFF01 <= cp <= 0xFF60 or
            0xFFE0 <= cp <= 0xFFE6):
            count += 2
        else:
            count += 1
    return count


# 無料アカウントの上限（余裕を持たせる）
TWITTER_LIMIT = 280
SAFE_LIMIT    = 270  # 少し余裕を持たせた上限


SYSTEM_PROMPT = """あなたは日本語AIアカウントを伸ばすコピーライターです。投稿を1本だけ書いてください。

━━━━━━━━━━━━━━━━━━━━
【絶対遵守の禁止事項】これを破ったら不採用
━━━━━━━━━━━━━━━━━━━━
1. 投稿本体を「」“”や引用符で囲まない。
   （プロンプトに書かれた引用記号を出力にコピーしない。本文だけを返す）
2. 抽象語の羅列を禁止。次の語は理由なく使わない：
   「革命的」「画期的」「劇的」「効率化」「最適化」「コミュニティの構築」
   「働き方が変わる」「将来性が失われる」「ビジネスチャンス」「時代に乗り遅れる」
3. 直訳調・造語の禁止。例：「普及激増」「採用の開始点」「最速成長」のような
   名詞+名詞を無理やり繋いだ表現や、英語をぎこちなく直訳した4字熟語は書かない。
4. 説明なしの固有名詞を出さない。「DeployCo」「Tomoro」のような耳慣れない名前を
   出すときは、必ず1行内で「DeployCo（企業向けAI導入会社）」のように
   括弧で意味を添える。
5. 「フォローして時代に乗り遅れるな」「将来性が失われる」など押し付け煽りは使わない。

━━━━━━━━━━━━━━━━━━━━
【絶対必須の条件】
━━━━━━━━━━━━━━━━━━━━
1. 本文に「数字 or 固有名詞（社名・サービス名・機能名）」を最低1つ入れる。
   抽象的な3つの〜ではなく「Bain・McKinseyなど19社」のように具体名で。
2. 日本語のみで60〜120文字（X換算120〜240）。
3. 絵文字は本文に最大2個＋文末1個（合計3個まで）。
4. 自然な日本語の話し言葉。声に出して読んで違和感がなければOK。
5. 投稿を見た人が「自分にどんな得があるか」を3秒で分かる形に。

━━━━━━━━━━━━━━━━━━━━
【良い投稿の例】（このトーン・粒度を真似る）
━━━━━━━━━━━━━━━━━━━━
例A（速報）：
【速報】OpenAIがDeployCo（企業向けAI導入会社）を設立🚨
McKinsey・Bain含む19社が参加し、Tomoro買収で約150名の導入専門人材を投入。
AIが「特別なもの」から業務インフラに変わる転換点です。

例B（Tips）：
ChatGPTを「来週金曜の美容院予約して」と頼むだけで、検索→比較→予約まで全部やる。
タスクモードを使うとカレンダー連携まで自動。手作業30分→2分。

━━━━━━━━━━━━━━━━━━━━
【NG例】これと同じ間違いをしない
━━━━━━━━━━━━━━━━━━━━
× 「【速報】ChatGPT普及激増🚀／35歳以上ユーザー最速成長／革命的AI採用の開始点」
   → 直訳調の造語、抽象的な結論で何が起きたか不明。
× 「【保存版】OpenAI学生クラブの3つのメリット／1.AIツールのアクセス／
   2.イベントの開催／3.コミュニティの構築」
   → どのツール？どんなイベント？具体性ゼロ。
× 「『【必見】DeployCoを知らないと将来性が失われる』」
   → 投稿全体を引用符で囲んでいる、固有名詞の説明なし、煽りが空回り。

━━━━━━━━━━━━━━━━━━━━
【書く前に自分に問う3つ】
━━━━━━━━━━━━━━━━━━━━
1. 数字か具体的な固有名詞、最低1つ入っているか？
2. 日本語ネイティブが音読して違和感ないか？
3. 「で、何が起きたの？」に1行で答えられているか？"""


def build_prompt(news_item: Dict, style: str) -> str:
    """スタイルに応じたプロンプトを生成"""

    ctx = get_analysis_context()
    viral = random.choice(ctx["viral_examples"])
    hook = random.choice(BUZZ_PATTERNS["hooks"])
    cta = random.choice(BUZZ_PATTERNS["cta_patterns"])

    base = f"""
ニュース情報：
タイトル: {news_item.get('title', '')}
内容: {news_item.get('summary', '')}
出典: {news_item.get('source', '')}

バズった実例（参考にすること）：
{viral['text']}
→ インプレッション: {viral['impressions']}

推奨フック: 「{hook}」
推奨CTA: 「{cta}」

⚠️ 重要: 日本語は2文字換算。投稿全体で120文字以内に収めること（X無料アカウント制限）。
"""

    if style == "breaking":
        return base + """
【速報型】で投稿を1本書いてください。
- 1行目は 【速報】 で始める（引用符は付けない）
- 2〜3行で「何が起きたか」を、社名・サービス名・数字を含めて具体的に
- 最後の1行で「だから何が変わるか」を自分の言葉で1行
- CTAは入れても入れなくても良いが、入れるなら控えめに（押し付けない）
- 合計 日本語60〜120文字（X換算120〜240）"""

    elif style == "tips":
        return base + """
【Tips型】で投稿を1本書いてください。
- 1行目で「誰得か」を一言で示す（【保存版】等の見出しは任意）
- 具体的な操作・コマンド・機能名を番号付き2〜3個（抽象的なメリットは禁止）
- 「手作業30分→2分」のように Before/After の数字を1か所入れる
- CTAは控えめに、または無くてもよい
- 合計 日本語60〜120文字（X換算120〜240）"""

    elif style == "alert":
        return base + """
【気づき型】で投稿を1本書いてください。
- 過度な煽り・脅し（「乗り遅れるな」「将来性が失われる」）は禁止
- 1行目で「多くの人が見落としている事実」を具体的に提示
- 2〜3行でその根拠（数字または具体例）を示す
- 最後の1行で読者が今日できる小さなアクションを1つ
- 合計 日本語60〜120文字（X換算120〜240）"""

    elif style == "story":
        return base + """
【共感・体験型】で投稿を1本書いてください。
- 1行目で「ある場面」を具体的に描写（実は〜／○○してたら〜）
- Before→After を具体的な数字・所要時間・成果物で表現
- 押し付けがましい教訓・CTAは避ける
- 合計 日本語60〜120文字（X換算120〜240）"""

    return base


def generate_post(news_item: Dict, style: Optional[str] = None):
    """
    ニュース記事からバズる投稿を生成する

    Returns:
        (post_text, style, twitter_char_count)
    """
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    if style is None:
        weights = {"breaking": 0.4, "tips": 0.3, "alert": 0.2, "story": 0.1}
        style = random.choices(list(weights.keys()), weights=list(weights.values()))[0]

    prompt = build_prompt(news_item, style)

    print(f"  ✍️  [{style}] {news_item['title'][:45]}...")

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ],
        max_tokens=400,
        temperature=0.7,
    )

    post_text = response.choices[0].message.content.strip()

    # X換算文字数で制限チェック・カット
    tw_len = twitter_len(post_text)
    if tw_len > SAFE_LIMIT:
        # 文字数がオーバーしている場合、末尾から削って収める
        while twitter_len(post_text) > SAFE_LIMIT - 6 and post_text:
            post_text = post_text[:-1]
        post_text = post_text.rstrip() + "…"

    return post_text, style, twitter_len(post_text)


def generate_daily_posts(news_items: list, count: int = 3) -> list:
    """
    1日分の投稿を生成する（スタイルをバランスよく配分）
    """
    styles = ["breaking", "tips", "alert", "story"]
    results = []

    for i, news in enumerate(news_items[:count]):
        style = styles[i % len(styles)]
        try:
            post, used_style, tw_count = generate_post(news, style=style)
            results.append({
                "post": post,
                "style": used_style,
                "news": news,
                "char_count": len(post),        # Python文字数（表示用）
                "twitter_count": tw_count,       # X換算文字数
            })
            print(f"     → {len(post)}文字 / X換算{tw_count}文字")
        except Exception as e:
            print(f"  ❌ 生成エラー: {e}")
            continue

    return results


if __name__ == "__main__":
    import sys, io
    from dotenv import load_dotenv
    load_dotenv()
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    test_news = {
        "title": "OpenAI、GPT-5を正式発表 — 推論能力が前世代比3倍に",
        "summary": "OpenAIがGPT-5を発表。数学・コーディング・科学分野での推論能力が大幅向上。API提供も開始。",
        "source": "OpenAI",
    }

    print(f"X無料アカウント上限: {TWITTER_LIMIT}（日本語のみ換算: 約140文字）\n")

    for style in ["breaking", "tips", "alert", "story"]:
        print(f"\n{'='*55}")
        print(f"スタイル: {style}")
        print("="*55)
        post, _, tw_count = generate_post(test_news, style=style)
        print(post)
        print(f"\nPython文字数: {len(post)} / X換算文字数: {tw_count} / 上限: {TWITTER_LIMIT}")
