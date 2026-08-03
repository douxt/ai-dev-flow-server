#!/usr/bin/env python3
"""
QQ邮箱电子发票PDF批量下载

用法:
  QQMAIL_EMAIL=douxt@qq.com QQMAIL_AUTH_CODE=xxx python3 scripts/download-qqmail-invoices.py
  QQMAIL_CUTOFF="2026-08-01" QQMAIL_SENDER=fapio python3 scripts/download-qqmail-invoices.py

环境变量:
  QQMAIL_EMAIL      必填，QQ邮箱地址
  QQMAIL_AUTH_CODE  必填，IMAP授权码（非QQ密码）
  QQMAIL_SENDER     发件人过滤关键词，默认 fapiao
  QQMAIL_CUTOFF     截止日期 YYYY-MM-DD，默认 2026-08-01
  QQMAIL_KEYWORD    附件文件名关键词，默认 电子发票
  QQMAIL_SAVE_DIR   保存目录，默认 ~/发票PDF下载

注意:
  QQ邮箱 IMAP 不支持 SINCE/SENTSINCE 搜索，脚本会客户端过滤日期。
  详见 memory/qqmail-imap-date-filter-silent-fail.md
"""
import imaplib
import email
import os
from email.header import decode_header
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone

IMAP_SERVER = os.environ.get("QQMAIL_IMAP", "imap.qq.com")
EMAIL = os.environ["QQMAIL_EMAIL"]
AUTH_CODE = os.environ["QQMAIL_AUTH_CODE"]
SENDER = os.environ.get("QQMAIL_SENDER", "fapiao")
SAVE_DIR = os.path.expanduser(os.environ.get("QQMAIL_SAVE_DIR", "~/发票PDF下载"))
CUTOFF_STR = os.environ.get("QQMAIL_CUTOFF", "2026-08-01")
KEYWORD = os.environ.get("QQMAIL_KEYWORD", "电子发票")

CUTOFF = datetime.strptime(CUTOFF_STR, "%Y-%m-%d").replace(tzinfo=timezone.utc)
os.makedirs(SAVE_DIR, exist_ok=True)


def decode_str(s):
    if s is None:
        return ""
    parts = decode_header(s)
    result = []
    for part, charset in parts:
        if isinstance(part, bytes):
            try:
                result.append(part.decode(charset or "utf-8", errors="ignore"))
            except LookupError:
                result.append(part.decode("utf-8", errors="ignore"))
        else:
            result.append(part)
    return "".join(result)


def main():
    print(f"连接 {IMAP_SERVER}...")
    mail = imaplib.IMAP4_SSL(IMAP_SERVER)
    mail.login(EMAIL, AUTH_CODE)
    mail.select("INBOX")

    # QQ邮箱 IMAP 不支持 SINCE/SENTSINCE，客户端过滤日期
    print(f"搜索发件人 {SENDER}（QQ邮箱 IMAP 不支持日期搜索，将客户端过滤）...")
    status, data = mail.search(None, f'(FROM "{SENDER}")')
    msg_ids = data[0].split()
    print(f"共 {len(msg_ids)} 封，逐封检查日期（先拉头后拉体）...\n")

    downloaded = 0
    skipped_date = 0
    skipped_no_match = 0

    for mid in msg_ids:
        # 第一步：只拉邮件头，检查日期
        _, header_data = mail.fetch(mid, "(RFC822.HEADER)")
        header_msg = email.message_from_bytes(header_data[0][1])

        try:
            msg_date = parsedate_to_datetime(header_msg["Date"])
            if msg_date.tzinfo is None:
                msg_date = msg_date.replace(tzinfo=timezone.utc)
        except Exception:
            skipped_date += 1
            continue

        if msg_date < CUTOFF:
            skipped_date += 1
            continue

        # 第二步：日期符合，拉完整邮件
        _, msg_data = mail.fetch(mid, "(RFC822)")
        full_msg = email.message_from_bytes(msg_data[0][1])

        found = False
        for part in full_msg.walk():
            filename = part.get_filename()
            if not filename:
                continue
            fname = decode_str(filename)
            if fname.lower().endswith(".pdf") and KEYWORD in fname:
                found = True
                filepath = os.path.join(SAVE_DIR, fname)
                base, ext = os.path.splitext(fname)
                counter = 1
                while os.path.exists(filepath):
                    filepath = os.path.join(SAVE_DIR, f"{base}_{counter}{ext}")
                    counter += 1
                payload = part.get_payload(decode=True)
                with open(filepath, "wb") as f:
                    f.write(payload)
                downloaded += 1
                print(f"  [{downloaded}] {msg_date.strftime('%m-%d %H:%M')}  {fname}  ({len(payload)} bytes)")

        if not found:
            skipped_no_match += 1

    mail.logout()
    print(f"\n===== 完成 =====")
    print(f"下载: {downloaded} 个PDF")
    print(f"跳过(日期不符): {skipped_date}")
    print(f"跳过(无匹配附件): {skipped_no_match}")
    print(f"保存位置: {SAVE_DIR}")


if __name__ == "__main__":
    main()
