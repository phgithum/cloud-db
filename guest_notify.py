# -*- coding: utf-8 -*-
"""游客进入通知：读取 cloud-db/guests.json，把未通知的游客请求发邮件，然后标记已通知。
由 .github/workflows/guest-notify.yml 每 3 分钟跑一次。
环境变量：SMTP_USER、SMTP_PASS、GH_TOKEN（仓库自带 GITHUB_TOKEN 即可）。
"""
import base64, json, os, smtplib, ssl
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from email.header import Header
import urllib.request

REPO = "phgithum/cloud-db"
PATH = "guests.json"
API = f"https://api.github.com/repos/{REPO}/contents/{PATH}"
TO = os.environ.get("SMTP_USER", "2339553665@qq.com")
CST = timezone(timedelta(hours=8))

def gh_req(method, body=None):
    token = os.environ.get("GH_TOKEN", "")
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(API, data=data, method=method, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "User-Agent": "guest-notify",
        "Content-Type": "application/json",
    })
    with urllib.request.urlopen(r, timeout=30) as resp:
        raw = resp.read().decode()
        return json.loads(raw) if raw else {}

def send_mail(subject, text):
    msg = MIMEText(text, "plain", "utf-8")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = TO
    msg["To"] = TO
    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.qq.com", 465, context=ctx) as s:
        s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASS"])
        s.sendmail(TO, [TO], msg.as_string())

def main():
    old = gh_req("GET")
    sha = old.get("sha")
    data = json.loads(base64.b64decode(old["content"]))
    reqs = data.get("requests", [])
    changed = False
    keep = []
    cutoff = (datetime.now(CST) - timedelta(days=7)).isoformat()
    for r in reqs:
        if r.get("notified"):
            # 超过 7 天的旧记录直接清掉
            if r.get("time", "") >= cutoff:
                keep.append(r)
            else:
                changed = True
            continue
        t = r.get("time", "")
        try:
            local = datetime.fromisoformat(t.replace("Z", "+00:00")).astimezone(CST).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            local = t
        site = r.get("site", "-")
        name = r.get("name") or "匿名"
        gid = r.get("gid", "-")
        try:
            send_mail(
                f"🔔 游客访问通知 · {site}",
                f"有游客进入了你的页面：\n\n"
                f"页面：{site}\n姓名/单位：{name}\n访问编号：{gid}\n时间：{local}\n\n"
                f"如需延长该游客的使用时间，请到聚合后台 → 游客授权 操作。",
            )
            print("sent:", gid, site, name)
        except Exception as e:
            print("mail failed:", e)
            keep.append(r)  # 没发出去，下次再试
            continue
        r["notified"] = True
        keep.append(r)
        changed = True
    if changed:
        data["requests"] = keep
        gh_req("PUT", {
            "message": "guest notify: mark sent",
            "branch": "main",
            "sha": sha,
            "content": base64.b64encode(json.dumps(data, ensure_ascii=False, indent=2).encode()).decode(),
        })
        print("guests.json updated")
    else:
        print("nothing to send")

if __name__ == "__main__":
    main()
