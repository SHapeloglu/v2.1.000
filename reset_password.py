#!/usr/bin/env python3
"""
reset_password.py — MailSender Pro Komut Satırı Şifre Sıfırlama Aracı
======================================================================
Mail erişimi olmadan veya acil durumda şifreyi doğrudan DB'de günceller.

Kullanım:
    python reset_password.py                      # Etkileşimli mod
    python reset_password.py admin yenisifre123   # Doğrudan güncelleme
    python reset_password.py --list               # Kullanıcıları listele

Örnekler:
    python reset_password.py admin admin123
    python reset_password.py --list
"""
import sys
import os
import pathlib

# Uygulama dizinini path'e ekle
BASE_DIR = pathlib.Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv
load_dotenv(BASE_DIR / '.env')

# DB bağlantısı var mı kontrol
required_env = ['DB_HOST', 'DB_USER', 'DB_PASSWORD', 'DB_NAME']
missing = [k for k in required_env if not os.getenv(k)]
if missing:
    print(f"❌ .env dosyasında eksik değişkenler: {', '.join(missing)}")
    sys.exit(1)

import database as db_module


def list_users():
    """Aktif kullanıcıları listeler."""
    conn = db_module.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, username, email, role, is_active, last_login FROM users ORDER BY id"
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    if not rows:
        print("Henüz kullanıcı yok.")
        return

    print(f"\n{'ID':<4} {'Kullanıcı Adı':<20} {'E-posta':<30} {'Rol':<10} {'Aktif':<6}")
    print("─" * 75)
    for r in rows:
        aktif = "✓" if r['is_active'] else "✗"
        email = r.get('email') or '—'
        print(f"{r['id']:<4} {r['username']:<20} {email:<30} {r['role']:<10} {aktif:<6}")
    print()


def reset_password(username: str, new_password: str) -> bool:
    """Kullanıcı şifresini doğrudan DB'de günceller."""
    import bcrypt

    # Kullanıcıyı bul
    user = db_module.get_user_by_username(username)
    if not user:
        print(f"❌ '{username}' kullanıcısı bulunamadı.")
        return False

    # Hash'le ve güncelle
    pw_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    conn = db_module.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET password_hash=%s WHERE username=%s",
                (pw_hash, username)
            )
        conn.commit()
        print(f"✅ '{username}' kullanıcısının şifresi başarıyla güncellendi.")
        return True
    except Exception as e:
        conn.rollback()
        print(f"❌ Güncelleme hatası: {e}")
        return False
    finally:
        conn.close()


def interactive_mode():
    """Etkileşimli şifre sıfırlama."""
    import getpass

    print("\n🔐 MailSender Pro — Şifre Sıfırlama")
    print("─" * 40)
    list_users()

    username = input("Kullanıcı adı: ").strip()
    if not username:
        print("❌ Kullanıcı adı boş olamaz.")
        return

    while True:
        password = getpass.getpass("Yeni şifre (görünmez): ")
        if len(password) < 6:
            print("⚠  Şifre en az 6 karakter olmalı. Tekrar deneyin.")
            continue
        confirm = getpass.getpass("Şifreyi tekrar girin: ")
        if password != confirm:
            print("⚠  Şifreler eşleşmiyor. Tekrar deneyin.")
            continue
        break

    reset_password(username, password)


def main():


    """Komut satırı argümanlarını ayrıştırır ve uygun modu çalıştırır."""
    args = sys.argv[1:]

    if not args:
        interactive_mode()
        return

    if args[0] == '--list' or args[0] == '-l':
        list_users()
        return

    if len(args) == 2:
        username, password = args
        if len(password) < 6:
            print("❌ Şifre en az 6 karakter olmalı.")
            sys.exit(1)
        ok = reset_password(username, password)
        sys.exit(0 if ok else 1)

    print(__doc__)
    sys.exit(1)


if __name__ == '__main__':
    main()
