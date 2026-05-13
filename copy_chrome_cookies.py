"""
Chromeのログイン済みクッキーをPlaywrightプロファイルにコピーする
（X へのログインをスキップできる）
"""
import os, sys, io, json, shutil, sqlite3, base64, time
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# --- パス設定 ---
CHROME_USER_DATA = Path(os.environ["LOCALAPPDATA"]) / "Google" / "Chrome" / "User Data"
COOKIE_DB_PATH   = CHROME_USER_DATA / "Default" / "Network" / "Cookies"
LOCAL_STATE_PATH = CHROME_USER_DATA / "Local State"
PLAYWRIGHT_PROFILE = Path(__file__).parent / "playwright_profile"
OUTPUT_COOKIES   = Path(__file__).parent / "x_cookies.json"

TARGET_DOMAIN = ".x.com"
KEY_COOKIES   = ["auth_token", "ct0", "twid"]   # X の認証に必要なクッキー

def get_chrome_encryption_key():
    """Chromeのクッキー暗号化キーを取得（Windows DPAPI で復号）"""
    with open(LOCAL_STATE_PATH, "r", encoding="utf-8") as f:
        local_state = json.load(f)
    encrypted_key_b64 = local_state["os_crypt"]["encrypted_key"]
    encrypted_key = base64.b64decode(encrypted_key_b64)[5:]  # 先頭5バイト "DPAPI" を除く

    # Windows DPAPI で復号
    import ctypes, ctypes.wintypes
    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", ctypes.wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    p = ctypes.create_string_buffer(encrypted_key, len(encrypted_key))
    blobin = DATA_BLOB(ctypes.sizeof(p), p)
    blobout = DATA_BLOB()
    retval = ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(blobin), None, None, None, None, 0, ctypes.byref(blobout)
    )
    if not retval:
        raise RuntimeError("DPAPI 復号に失敗しました")
    result = ctypes.string_at(blobout.pbData, blobout.cbData)
    ctypes.windll.kernel32.LocalFree(blobout.pbData)
    return result


def decrypt_cookie_value(encrypted_value: bytes, key: bytes) -> str:
    """Chrome のクッキー値を復号（AES-256-GCM）"""
    if not encrypted_value:
        return ""
    if encrypted_value[:3] == b"v10" or encrypted_value[:3] == b"v11":
        # AES-256-GCM（Chrome 80+）
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            nonce = encrypted_value[3:3+12]
            ciphertext = encrypted_value[3+12:]
            aesgcm = AESGCM(key)
            return aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8")
        except Exception:
            return ""
    else:
        # 古い形式（DPAPIで直接暗号化）
        try:
            import ctypes, ctypes.wintypes
            class DATA_BLOB(ctypes.Structure):
                _fields_ = [("cbData", ctypes.wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]
            p = ctypes.create_string_buffer(encrypted_value, len(encrypted_value))
            blobin = DATA_BLOB(ctypes.sizeof(p), p)
            blobout = DATA_BLOB()
            ctypes.windll.crypt32.CryptUnprotectData(
                ctypes.byref(blobin), None, None, None, None, 0, ctypes.byref(blobout)
            )
            result = ctypes.string_at(blobout.pbData, blobout.cbData)
            ctypes.windll.kernel32.LocalFree(blobout.pbData)
            return result.decode("utf-8")
        except Exception:
            return ""


def extract_x_cookies():
    """ChromeのDBからX用クッキーを抽出して返す"""
    if not COOKIE_DB_PATH.exists():
        raise FileNotFoundError(f"Chromeのクッキーが見つかりません: {COOKIE_DB_PATH}")

    # Chrome が起動中だとDBがロックされるので別名でコピーして使う
    import tempfile
    tmp_db = Path(tempfile.mktemp(suffix=".db"))
    # ロック回避：共有読み取りモードでコピー
    with open(COOKIE_DB_PATH, "rb") as src, open(tmp_db, "wb") as dst:
        dst.write(src.read())

    try:
        key = get_chrome_encryption_key()
        conn = sqlite3.connect(tmp_db)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name, CAST(encrypted_value AS BLOB), host_key, path, expires_utc, is_secure, is_httponly
            FROM cookies
            WHERE host_key LIKE '%x.com%' OR host_key LIKE '%twitter.com%'
        """)
        rows = cursor.fetchall()
        conn.close()
    finally:
        try:
            tmp_db.unlink(missing_ok=True)
        except Exception:
            pass

    cookies = []
    for name, enc_value, host_key, path, expires, secure, httponly in rows:
        value = decrypt_cookie_value(enc_value, key)
        if not value:
            continue
        cookies.append({
            "name": name,
            "value": value,
            "domain": host_key,
            "path": path,
            "secure": bool(secure),
            "httpOnly": bool(httponly),
            "sameSite": "None",
        })

    return cookies


def inject_cookies_to_playwright(cookies: list):
    """Playwrightのプロファイルにクッキーを注入（ブラウザ起動して設定）"""
    from playwright.sync_api import sync_playwright

    PLAYWRIGHT_PROFILE.mkdir(exist_ok=True)

    with sync_playwright() as p:
        # Playwright内蔵Chromiumで起動（ChromeのUDが不要）
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = browser.new_context()
        ctx.add_cookies(cookies)

        # クッキーが有効か確認
        page = ctx.new_page()
        page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=15000)
        time.sleep(2)
        url = page.url
        browser.close()

        if "login" in url:
            return False
        return True


if __name__ == "__main__":
    print("=== Chrome → Playwright クッキー移行ツール ===\n")

    # cryptography ライブラリの確認
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError:
        print("cryptography ライブラリをインストールします...")
        import subprocess
        subprocess.run(["venv\\Scripts\\pip.exe", "install", "cryptography"], check=True)

    print("1. Chromeのクッキーを読み取り中...")
    try:
        cookies = extract_x_cookies()
        key_found = [c for c in cookies if c["name"] in KEY_COOKIES]
        print(f"   X用クッキー: {len(cookies)}件取得 / 認証クッキー: {len(key_found)}件")

        if not key_found:
            print("\n❌ X のログイン情報が見つかりません。")
            print("   ChromeでX(x.com)にログインしてから再実行してください。")
            sys.exit(1)

    except Exception as e:
        print(f"❌ エラー: {e}")
        sys.exit(1)

    # JSON保存（Playwright用）
    with open(OUTPUT_COOKIES, "w", encoding="utf-8") as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)
    print(f"\n2. クッキーを保存: {OUTPUT_COOKIES}")

    print("\n3. Playwrightでログイン確認中...")
    try:
        ok = inject_cookies_to_playwright(cookies)
        if ok:
            print("   ✅ X へのログイン成功！")
        else:
            print("   ⚠️  ログインページにリダイレクトされました。Chromeで再ログインしてください。")
    except Exception as e:
        print(f"   ⚠️  確認中にエラー: {e}")
        print("   （クッキーは保存済みなので次のステップに進めます）")

    print("\n✅ 完了！次回からXを自動スクレイピングできます。")
