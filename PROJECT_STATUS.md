# AI X Bot — プロジェクト状況メモ

**最終更新**: 2026-05-15  
**ステータス**: 🔍 **制限解除検知モード**（オリジナル投稿停止・返信のみauto試行で X側のリプライ制限解除を毎日チェック）  
**リポジトリ**: https://github.com/zenosynead-star/ai-x-bot (public — Streamlit Cloud デプロイのため)  
**管理画面**: https://ai-x-bot-dashboard.streamlit.app/

## 現在の運用モード（2026-05-15〜）

```
オリジナル投稿: 🛑 一時停止（MAX_POSTS_PER_DAY=0）
返信       : ✅ 毎日5件リプライ試行（REPLY_MODE=reply）
              ├─ 成功 → 本来のリプライとしてXに届く（制限解除のサイン）
              └─ 403 → 何もしない（X上に何も投稿されない、ゴミ投稿を出さない）
コスト      : 約5円/日（返信生成のみ・実投稿は制限中ならゼロ）
目的        : 1年休眠アカウントのリプライ制限解除を検知
```

**注意**: 制限解除されるまでXには返信が一切表示されない（投稿ゼロ）。これは意図通り。
メンション投稿フォールバックは廃止（タグ付け投稿になり「リプライじゃないゴミ」が出てしまうため）。

**制限解除を確認したらすぐに再開**:
- `daily.yml` の `MAX_POSTS_PER_DAY: '0'` を `'3'` に戻して push（オリジナル投稿再開）
- 必要なら `REPLY_MODE: 'reply'` を `'auto'` に戻すことも可能

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

### 自動返信が403エラーになる → 2026-05-14 メンション投稿で回避達成
- **原因**: 新規Xアカウントは `in_reply_to_tweet_id` 指定のリプライ送信をXがブロック
- **回避策（採用）**: `REPLY_MODE=mention` で `in_reply_to_tweet_id` を指定せず、
  本文先頭に `@username` を付けた通常投稿として送る。403が発生しない。
  - トレードオフ: 相手のリプライ欄ではなくメンション欄に表示される
  - 効果: 通知は同様に届くのでフォロワー獲得効果はある程度維持
- **設定**: `daily.yml` の env に `REPLY_MODE: 'mention'` を設定済み
- **コード**: `x_poster.py` の `post_replies()` で `REPLY_MODE` を読み分岐
- **動作確認**: 2026-05-14 02:34 の本番実行 (run #25838256724) で 5/5件メンション成功

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

1. ✅ ~~自動返信の403回避~~ (2026-05-14 REPLY_MODE=mention で達成)
2. ✅ ~~ターゲットアカウントを見直す~~ (URLフィルタ緩和で対応済み 2026-05-13)
3. ✅ ~~スケジューラー常駐設定~~ (2026-05-14 GitHub Actions cron)
4. ✅ ~~管理画面の構築~~ (2026-05-14 Streamlit 5ページ実装)
5. ✅ ~~Streamlit Cloud デプロイ~~ (2026-05-15 完了、https://ai-x-bot-dashboard.streamlit.app/)
6. **プロフィール最適化** — アイコン・自己紹介・固定ツイートを設定して流入を受け取れる状態に
7. **cron 遅延の改善（任意）** — GitHub Actions cron はベストエフォートで遅延あり（5/14 は UTC 22:00→08:08 で約10時間遅延）。気になるなら Render Cron Jobs 等に移行
8. **将来検討** — リプライ制限が解除されたら REPLY_MODE=reply に戻すか比較検証

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

## 2026-05-14〜15 の実績

### 2026-05-14 深夜 — メンション投稿で 403 を完全回避
- `x_poster.py` に `REPLY_MODE=mention` 分岐を追加。`in_reply_to_tweet_id` を指定せず本文先頭に `@username` を付ける通常投稿として送信
- `daily.yml` の env に `REPLY_MODE: 'mention'` を固定
- 02:34 JST 本番テスト (run #25838256724): メンション 5/5 件 + オリジナル投稿 3/3 件、**計8件すべて X に投稿成功**
- コスト約 $0.12（約18円）

### 2026-05-14 朝の cron 自動実行
- **JST 17:08 に実行 (run #25849289422)**: cron 式は `0 22 * * *` (UTC 22:00 = JST 07:00) だが GitHub Actions のベストエフォートで約10時間遅延
- 結果: メンション 5/5 + オリジナル 3/3 件成功、自動運用が機能していることを確認

### 2026-05-15 — Streamlit Cloud デプロイ
- リポジトリを **public** に変更（Streamlit Cloud の OAuth スコープが `public_repo` のみ対応のため、private のままでは「This repository does not exist」になる）
- 最初の deploy で Main file path が `news_fetcher.py` に誤設定される事故。Settings 経由では変更不可なので、アプリを Delete して再 Deploy
- 全 `__main__` ブロック内の `sys.stdout = io.TextIOWrapper(...)` を try/except + `/mount/src/` 早期終了でガード（Streamlit Cloud が依存解析で他 Python ファイルを誤実行する挙動への対策）
- **公開 URL**: https://ai-x-bot-dashboard.streamlit.app/
- 5ページ動作確認済み: ダッシュボード / 手動実行 / 投稿プレビュー / 返信履歴 / スケジュール設定

### 2026-05-15 — REPLY_MODE=auto（ハイブリッド）実装
- ユーザーから「X の返信欄を見ても返信ではなく単なるメンション投稿になっている」と指摘
- `x_poster.py` の `post_replies()` を改造：
  - `auto`: まず in_reply_to_tweet_id 指定でリプライを試行 → 403 ならメンション投稿で再送
  - X の制限が解除されたら **コード変更不要で自動的に本来のリプライに移行する**
- `daily.yml` の env を `REPLY_MODE: 'auto'` に変更
- 02:28 JST 本番テスト (run #25896953243): リプライ 0/5 (全件403) → メンションフォールバック 5/5 成功
- **現状: 制限はまだ継続中。1週間以上の人間らしい活動でX側が解除する見込み**

### アカウント育成プラン（リプライ制限解除を促す）

**アカウント状況（ハンディキャップ）**:
- アカウント年齢: 約1年
- 過去1年の活動: ほぼ休眠状態（ツイート数桁、フォロワー一桁）
- 2026-05-13 から急に API で1日8件の自動投稿開始
- → X からは典型的な **「Bot 化された休眠アカウント」** に見える
- → 新規垢より厳しく扱われる可能性あり、1週間では解除されない見込み

**期間目安**: 2-3週間（最低でも2週間、状況によって3週間以上）

**Week 1 / 土台作り**:
- プロフィール完成（アイコン・ヘッダー・自己紹介160字・固定ツイート）
- 自分発信ツイート 1〜2件/日
- いいね 5〜10件/日
- 手動リプライ 1〜2件/日（ボットじゃなく自分の言葉で）
- フォロー 5〜10人/日
- **重要**: ブラウザ or モバイルアプリで定期ログイン（API経由じゃない「人間としてのログイン履歴」を増やす）

**Week 2-3 / 継続 + ペース増し**:
- 同じルーティンを継続
- 可能ならリアル友人/知人に相互フォローしてもらう（早期解除の強力なシグナル）
- 既にフォロワーがいる別アカウントから紹介ツイートしてもらう

**3週間後の目標値**:
- フォロー 80〜150人
- フォロワー 20〜50人
- 自分発信ツイート総数 30件以上
- 累計いいね 200件以上
- ブラウザ/アプリのログイン履歴あり

**確認方法**:
- `gh run view <最新run-id> --repo zenosynead-star/ai-x-bot --log | findstr "mode"` で `mode: reply` が出始めれば成功
- Streamlit の「💬 返信履歴」で ✅ 送信成功 (リプライ成功) の件数が増えていれば制限解除のサイン
- 解除されない場合の最終手段: X API Basic プラン ($200/月) へのアップグレード

---

## 既知の制約・注意

### GitHub Actions の cron 遅延
- 無料 Actions の cron はベストエフォート、最大数時間〜10時間の遅延あり
- 「JST 07:00 ぴったり」を保証したいなら Render Cron Jobs 等への移行検討

### Streamlit Cloud は private repo 不可
- OAuth スコープが `public_repo` のみ。private にすると deploy できない
- リポジトリは public のまま運用。API キーは Secrets で完全に保護

### Streamlit Cloud は `__main__` ブロックを誤実行
- リポジトリ内の他 Python ファイルを依存解析で実行することがある
- 全 `__main__` ブロックを `/mount/src/` 検出 + try/except でガード済み
