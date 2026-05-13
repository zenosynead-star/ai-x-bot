"""
返信文生成モジュール
大手AIアカウントへの「フォロワーを引き寄せる返信」を生成する
"""

import os
from groq import Groq


REPLY_SYSTEM_PROMPT = """あなたはX（Twitter）でフォロワー0から急成長させるための返信専門家です。

【返信の目的】
大手AIアカウント（1万〜20万フォロワー）の投稿に返信することで、
そのフォロワーたちに自分の存在を知らせ、プロフィールを見てもらい、フォローを獲得する。

【バズる返信の黄金ルール】
1. 元投稿の価値を認める（「これは重要！」）
2. 自分の視点・補足情報を1つ追加する（「自分も試したら〜」「補足すると〜」）
3. 質問で会話を続ける（「〜についてはどう思いますか？」）
4. 30〜80文字が最適（長すぎると読まれない）
5. 絵文字は1〜2個に抑える
6. 媚びすぎない・批判しない・自然体

【返信がバズる条件】
- 元投稿者が「いいね」してくれると一気に露出増
- フォロワーから「わかる！」「参考になった」と思われる内容
- 自分の専門性・視点が1行で伝わる

【絶対NG】
- 「参考になりました！」だけの薄い返信
- 長文返信（読まれない）
- 宣伝・URLの貼り付け
- 批判・反論"""


def generate_reply(original_post: dict) -> str:
    """
    元投稿に対するフォロワーを引き寄せる返信を生成

    Args:
        original_post: {"account": "@xxx", "text": "投稿本文", ...}

    Returns:
        返信テキスト（30〜80文字）
    """
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    prompt = f"""以下のX投稿への返信文を作成してください。

【元投稿】
アカウント: {original_post['account']}
内容:
{original_post['text']}

要件：
- 30〜60文字（日本語は2文字換算のため、X換算で60〜120以内に収めること）
- 元投稿の内容に関連した自分の視点・補足を1つ追加
- 最後に軽い質問か共感を入れる
- 絵文字1〜2個
- 自然な会話トーン
- 日本語のみで書く（中国語・英語は使わない）
- AIや仕事効率化に詳しいアカウントとしての視点で書く
- 「【返信】」「返信：」などのラベルは絶対に付けない
- 本文だけを出力する（説明・前置き不要）"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": REPLY_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        max_tokens=150,
        temperature=0.9,
    )

    return response.choices[0].message.content.strip()


def generate_replies_for_trends(trending_posts: list, count: int = 5) -> list:
    """
    トレンド投稿リストから返信を生成する

    Returns:
        [{"original": post, "reply": reply_text}, ...]
    """
    results = []
    top_posts = trending_posts[:count]

    print(f"  💬 返信文を{len(top_posts)}本生成中...")

    for post in top_posts:
        try:
            reply = generate_reply(post)
            results.append({
                "original_account": post["account"],
                "original_text": post["text"],
                "reply": reply,
                "engagement_score": post.get("engagement_score", 0),
                "tweet_id": post.get("tweet_id"),       # ← 返信先ツイートID
                "tweet_url": post.get("tweet_url"),     # ← 返信先URL
            })
            print(f"    ✅ {post['account']} への返信生成完了")
        except Exception as e:
            print(f"    ❌ エラー: {e}")

    return results
