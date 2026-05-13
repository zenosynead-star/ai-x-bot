# AI X Bot — プロジェクト状況メモ

**最終更新**: 2026-05-14  
**ステータス**: ☁️ GitHub Actions でクラウド常駐運用開始 / ⏳ 返信は新規アカウント制限中  
**リポジトリ**: https://github.com/zenosynead-star/ai-x-bot (private)

---

## 何が動いているか

| 機能 | 状態 | 備考 |
|------|------|------|
| トレンド収集 | ✅ 動作中 | X API v2で直接取得（Playwright不要） |
| 返信文生成 | ✅ 動作中 | Groq (llama-3.3-70b) 無料 |
| オリジナル投稿生成 | ✅ 動作中 | 3件/日、60〜120文字 |
| 自動投稿（オリジナル） | ✅ 動作中 | 本番投稿 ≒ 7円/日 |
| 自動返信 | ⏳ 制限中 | 新規アカウントのXスパム防止制限。数日〜1週間で解除見込み |
| HTMLレポート | ✅ 動作中 | コピーボタン＋ツイートリンクで手動返信も簡単 |

---

## 主要コマンド

### クラウド（GitHub Actions）
```powershell
# DRY RUN で手動テスト実行
gh workflow run daily.yml -f dry_run=true --repo zenosynead-star/ai-x-bot

# 本番モードで手動実行
gh workflow run daily.yml -f dry_run=false --repo zenosynead-star/ai-x-bot

# 実行履歴・ログ確認
gh run list --workflow=daily.yml --repo zenosynead-star/ai-x-bot
gh run view <run-id> --repo zenosynead-star/ai-x-bot --log

# Secrets 一覧
gh secret list --repo zenosynead-star/ai-x-bot
```

自動実行: 毎日 UTC 22:00 = JST 07:00 に cron 起動

### ローカル（デバッグ用）
```powershell
# フル実行（収集 → 返信試行 → 投稿 → レポート）
venv\Scripts\python.exe main.py --scrape

# レポートのみ再生成（投稿なし・毎日の確認用）
venv\Scripts\python.exe main.py --report

# 自動返信のみ N 件テスト（403解除確認用）
venv\Scripts\python.exe main.py --test-reply 3
```

---

## ファイル構成

```
ai_x_bot/
├── main.py              # メインオーケストレーター
├── x_scraper.py         # X API v2でトレンド収集（Playwright廃止）
├── reply_generator.py   # Groqで返信文生成
├── post_generator.py    # Groqでオリジナル投稿生成
├── x_poster.py          # X API v2で実際に投稿
├── report_generator.py  # HTMLレポート生成
├── news_fetcher.py      # AIニュース収集
├── x_analyzer.py        # バズパターン分析データ
├── .env                 # APIキー（要保護）
├── today_trends.json    # 当日のトレンドキャッシュ
└── reports/             # 生成されたHTMLレポート
```

---

## .env の内容（キー名のみ）

```
GROQ_API_KEY=...
X_API_KEY=...
X_API_SECRET=...
X_ACCESS_TOKEN=...
X_ACCESS_TOKEN_SECRET=...
X_BEARER_TOKEN=...
MAX_POSTS_PER_DAY=3
POST_TIMES=07:30,12:30,19:00
DRY_RUN=False
```

---

## ターゲットアカウント（トレンド収集元）

```python
TARGET_ACCOUNTS = [
    "masahirochaen",   # 19.2万F
    "ctgptlb",         # 13.7万F
    "chatgptair",      # 10.8万F
    "SuguruKun_ai",    # 10.5万F
    "hashimoto_no14",  # 3.9万F
]
```

※ 2026-05-13 URLフィルタを緩和（URL除去後30文字以上ならOK）→ 5アカウント全部から3件ずつ収集できるようになった

---

## 既知の問題・対応状況

### 自動返信が403エラーになる
- **原因**: 新規Xアカウントは「エンゲージされていない相手への返信」をAPIでブロックされる  
  （`reply_settings=everyone` でも適用される、アカウント側の問題ではなくXの新規垢制限）
- **対処**: レポートの「📋 コピー」＋「🐦 ツイートを開く」で手動返信  
- **解除条件**: 数日〜1週間の通常活動（フォロワーが増えると自動的に解除される見込み）
- **テスト方法**: `venv\Scripts\python.exe main.py --test-reply 3`（件数省略時はデフォルト3件）
- **2026-05-13 再テスト**: 3件全滅（@chatgptair×2、@masahirochaen×1 すべて REPLY_RESTRICTED）。
  → アカウント全体の制限が継続中。最低でも1週間以上はかかる見込み。

### Playwright廃止
- Chrome 127+ のApp-Bound Encryption (v20) でcookie抽出不可になり廃止
- X API v2 (tweepy) に完全移行、Playwrightは不要

---

## 課金情報

| サービス | 料金 | 備考 |
|---------|------|------|
| Groq | 無料 | llama-3.3-70b-versatile |
| X API | ≒ $0.015/ツイート | Pay Per Use、約2円/件 |
| 1日あたり | 約3件 × $0.015 ≒ 約7円 | 返信が動くと最大8件 ≒ 約18円/日 |

---

## 次にやること（優先度順）

1. **1週間以上経ったら自動返信を再テスト** — `main.py --test-reply 3` で確認
2. ✅ ~~ターゲットアカウントを見直す~~ (URLフィルタ緩和で対応済み 2026-05-13。新規アカウント追加が必要になったら別途検討)
3. ✅ ~~スケジューラー常駐設定~~ (2026-05-14 GitHub Actions で対応済み、JST 07:00 cron 起動)
4. **プロフィール最適化** — アイコン・自己紹介・固定ツイートを設定して流入を受け取れる状態に
5. **管理画面の構築（将来）** — クラウドUIから時刻・ターゲット・返信内容を編集できる Streamlit / FastAPI を載せる

---

## 今日の実績（2026-05-13）

- オリジナル投稿3件を本番投稿 ✅
  - https://x.com/i/web/status/2054213914720948245
  - https://x.com/i/web/status/2054214420856029446
  - https://x.com/i/web/status/2054214926642893236
- 消費コスト: 約 $0.045（約7円）

### 夜の作業
- **投稿品質改善**: `post_generator.py` の SYSTEM_PROMPT を全面刷新（NG例追加・引用符禁止・抽象語禁止・固有名詞必須）、スタイル別プロンプトから引用符を除去、temperature 0.85→0.7。テスト出力で「ChatGPT普及激増」型の造語や引用符付き本文が消え、`Before30分→After2分` 型の具体数字が入るように。
- **自動返信再テスト**: `main.py --test-reply 3` を追加して3件試行 → 全件返信制限。アカウント全体の制限が継続中と確定。コスト約 $0.045（約7円・返信文生成のみ、投稿はXがブロック）
- **ターゲット見直し（URLフィルタ緩和）**: `x_scraper.py` line 94-101 を修正。URL除去後の本文が30文字以上なら採用に変更。`re` モジュール追加。5アカウント全部から3件ずつ計15件取れるように（Before: ctgptlb・SuguruKun_ai = 0件）
- **GitHub Actions でクラウド化**: リポジトリ `zenosynead-star/ai-x-bot` (private) を作成。`.github/workflows/daily.yml` で UTC 22:00 = JST 07:00 の cron + `workflow_dispatch` 手動実行（`dry_run` boolean input、手動時のデフォルトは true）。Secrets 6個（GROQ_API_KEY、X_API_KEY/SECRET/ACCESS_TOKEN/ACCESS_TOKEN_SECRET/BEARER_TOKEN）を `gh secret set --body` で登録（パイプ経由は BOM 混入で失敗するため要注意）。DRY RUN 手動テスト2回目で全STEP完走確認（run #25811689051）。
- **明朝 5/14 07:00 JST から本番自動運用開始**（DRY_RUN=false、3件のオリジナル投稿が自動投稿される。自動返信は新規垢制限のため0/5件のまま）
