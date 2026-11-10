#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自建微信群活码（自托管版）
------------------------------------------------------------
对外固定一个网址（活码扫这个网址），后台随时上传新的微信群二维码。
外面的活码永远不变，背后每 7 天换一次群码即可。
"""
import os
import io
import json
import datetime

from flask import (
    Flask, request, render_template_string, send_file,
    redirect, url_for, session, flash,
)
from PIL import Image

BASE = os.path.dirname(os.path.abspath(__file__))
# 默认数据放在 data/；若挂载了持久盘，设置环境变量 DATA_DIR 指向挂载路径即可持久化
DATA = os.environ.get("DATA_DIR", os.path.join(BASE, "data"))
os.makedirs(DATA, exist_ok=True)
CURRENT_QR = os.path.join(DATA, "current_qr.png")
META = os.path.join(DATA, "meta.json")

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "changeme123")
APP_NAME = os.environ.get("APP_NAME", "客户福利群")
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")

app = Flask(__name__)
app.secret_key = SECRET_KEY


# ------------------------- 元数据读写 -------------------------
def load_meta():
    if os.path.exists(META):
        try:
            with open(META, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"title": APP_NAME, "note": "", "updated_at": None, "expires_at": None}


def save_meta(m):
    with open(META, "w", encoding="utf-8") as f:
        json.dump(m, f, ensure_ascii=False, indent=2)


# ------------------------- 公开页（客户扫活码进来） -------------------------
PUBLIC_TPL = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>{{ m.title }} · 扫码进群</title>
<style>
  * { box-sizing: border-box; }
  body { margin:0; font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;
         background:#f2f4f7; color:#1f2329; display:flex; min-height:100vh;
         align-items:center; justify-content:center; padding:20px; }
  .card { background:#fff; border-radius:18px; padding:28px 22px; width:100%; max-width:360px;
          box-shadow:0 8px 30px rgba(0,0,0,.08); text-align:center; }
  h1 { font-size:21px; margin:0 0 14px; }
  .tip { color:#57606a; font-size:14px; margin:6px 0 14px; }
  .qr { width:62%; max-width:220px; height:auto; border:10px solid #fff;
        border-radius:14px; box-shadow:0 0 0 1px #eaecef; }
  .note { color:#1f2329; font-size:14px; margin:14px 4px 4px; white-space:pre-wrap; }
  .sub { color:#8a939e; font-size:12px; margin-top:14px; }
  .empty { color:#b23b3b; font-size:15px; padding:24px 0; }
</style>
</head>
<body>
  <div class="card">
    <h1>{{ m.title }}</h1>
    {% if has_qr %}
      <p class="tip">长按下方二维码，识别加入群聊</p>
      <img class="qr" src="/qr.png?t={{ now }}" alt="群二维码">
      {% if m.note %}<p class="note">{{ m.note }}</p>{% endif %}
      <p class="sub">如无法进群，请刷新本页重试</p>
    {% else %}
      <p class="empty">群二维码暂未配置，请联系商家</p>
    {% endif %}
  </div>
</body>
</html>"""


@app.route("/")
def index():
    m = load_meta()
    now = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    has_qr = os.path.exists(CURRENT_QR)
    return render_template_string(PUBLIC_TPL, m=m, now=now, has_qr=has_qr)


@app.route("/qr.png")
def qr():
    if not os.path.exists(CURRENT_QR):
        return ("尚未配置群二维码", 404)
    resp = send_file(CURRENT_QR, mimetype="image/png")
    resp.headers["Cache-Control"] = "no-store, max-age=0"
    return resp


# ------------------------- 后台（换群码） -------------------------
LOGIN_TPL = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>后台登录</title>
<style>body{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;
background:#f2f4f7;display:flex;min-height:100vh;align-items:center;justify-content:center}
.box{background:#fff;padding:26px;border-radius:14px;width:300px;box-shadow:0 8px 30px rgba(0,0,0,.08)}
h2{margin:0 0 14px;font-size:18px}.tip{color:#b23b3b;font-size:13px;margin:8px 0}
input[type=password],input[type=text]{width:100%;padding:9px;margin:6px 0 12px;border:1px solid #d0d4d9;border-radius:8px}
button{width:100%;padding:10px;background:#07c160;color:#fff;border:0;border-radius:8px;font-size:15px}</style>
</head><body><div class="box">
<h2>活码后台登录</h2>
{% with msgs = get_flashed_messages() %}{% if msgs %}<p class="tip">{{ msgs[0] }}</p>{% endif %}{% endwith %}
<form method="post"><input type="password" name="password" placeholder="管理密码" required>
<button>登录</button></form></div></body></html>"""


ADMIN_TPL = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>活码后台</title>
<style>body{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;background:#f2f4f7;margin:0;padding:20px}
.wrap{max-width:460px;margin:0 auto;background:#fff;padding:22px;border-radius:14px;box-shadow:0 8px 30px rgba(0,0,0,.08)}
h2{font-size:18px;margin:0 0 4px}.small{color:#8a939e;font-size:12px}
.ok{color:#07c160;font-size:13px;margin:8px 0}.tip{color:#b23b3b;font-size:13px;margin:8px 0}
label{display:block;font-size:13px;margin:14px 0 4px;color:#57606a}
input[type=text],input[type=file],textarea{width:100%;padding:9px;border:1px solid #d0d4d9;border-radius:8px;font-size:14px}
textarea{height:60px;resize:vertical}
button{margin-top:16px;width:100%;padding:11px;background:#07c160;color:#fff;border:0;border-radius:8px;font-size:15px}
.preview{margin:10px 0;text-align:center}.preview img{width:160px;border:1px solid #eee;border-radius:10px}
a{color:#57606a;font-size:13px}</style></head><body><div class="wrap">
<h2>活码后台</h2><p class="small">当前群码更新时间：{{ m.updated_at or '（未配置）' }}<br>
<a href="/">查看公开页</a> · <a href="/admin/logout">退出登录</a></p>
{% with msgs = get_flashed_messages() %}{% if msgs %}<p class="{% if '已' in msgs[0] %}ok{% else %}tip{% endif %}">{{ msgs[0] }}</p>{% endif %}{% endwith %}
{% if has_qr %}<div class="preview"><img src="/qr.png?t={{ now }}" alt="当前群码"></div>{% endif %}
<form method="post" enctype="multipart/form-data">
  <label>上传新的微信群二维码（7天一换，支持 PNG / JPG）</label>
  <input type="file" name="file" accept="image/*" required>
  <label>群名称 / 标题</label>
  <input type="text" name="title" value="{{ m.title }}">
  <label>说明文字（可选，显示在二维码下方）</label>
  <textarea name="note">{{ m.note }}</textarea>
  <label>预计过期时间（可选，仅作备注提醒）</label>
  <input type="text" name="expires_at" value="{{ m.expires_at or '' }}" placeholder="如 2026-11-17">
  <button>保存并更新群码</button>
</form>
<p class="small" style="margin-top:14px">提示：每 7 天在微信里重新生成群二维码后，回来这里上传一次即可，对外活码无需任何改动。</p>
</div></body></html>"""


@app.route("/admin", methods=["GET", "POST"])
def admin():
    # 登录
    if request.method == "POST" and "password" in request.form:
        if request.form["password"] == ADMIN_PASSWORD:
            session["admin"] = True
        else:
            flash("密码错误")
    if not session.get("admin"):
        return render_template_string(LOGIN_TPL)

    # 上传新群码
    if request.method == "POST" and "file" in request.files:
        f = request.files["file"]
        if f and f.filename:
            try:
                img = Image.open(f.stream).convert("RGB")
                img.save(CURRENT_QR, "PNG")
            except Exception as e:
                flash("图片读取失败：" + str(e))
                return redirect(url_for("admin"))
            m = load_meta()
            m["title"] = request.form.get("title", m.get("title", APP_NAME))
            m["note"] = request.form.get("note", "")
            m["expires_at"] = request.form.get("expires_at") or None
            m["updated_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            save_meta(m)
            flash("已更新群二维码")
        return redirect(url_for("admin"))

    m = load_meta()
    now = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    has_qr = os.path.exists(CURRENT_QR)
    return render_template_string(ADMIN_TPL, m=m, now=now, has_qr=has_qr)


@app.route("/admin/logout")
def logout():
    session.pop("admin", None)
    return redirect(url_for("admin"))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
