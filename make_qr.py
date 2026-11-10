#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成"固定活码"图片：把对外固定网址编码成二维码。
用法:
    python make_qr.py <对外网址> [输出文件名.png]
例如:
    python make_qr.py https://your-domain.example.com/ huoma.png
"""
import sys
import qrcode


def main():
    if len(sys.argv) < 2:
        print("用法: python make_qr.py <对外网址> [输出.png]")
        sys.exit(1)
    url = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else "huoma.png"
    img = qrcode.make(url)
    img.save(out)
    print("已生成固定活码:", out)
    print("该码指向网址:", url)
    print("把这个码印到海报/名片上，背后群码在后台随时换，此码永不改动。")


if __name__ == "__main__":
    main()
