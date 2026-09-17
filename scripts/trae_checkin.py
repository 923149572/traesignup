#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TraeCode 每日签到领取积分。

依赖环境变量 TRAE_TOKEN（建议放在 GitHub Secrets 中），
取值方式：登录 TraeCode 后从请求头里复制 Authorization 的值，
或只复制 Cloud-IDE-JWT 后面的 token 串。
"""

import json
import os
import sys
import urllib.error
import urllib.request

BASE_URL = "https://api.trae.cn/trae/api/v2/ug/checkin_credits"
STATUS_URL = f"{BASE_URL}/status"
CLAIM_URL = f"{BASE_URL}/claim"

# 接口字段名未公开，这里兼容几种常见的“已签到”标记
CHECKED_KEYS = (
    "checked_in",
    "checked",
    "signed",
    "signed_in",
    "is_checked_in",
    "is_signed",
    "today_checked",
    "today_signed",
    "has_checked_in",
    "claimed",
)
CHECKED_HINTS = ("already", "已签到", "repeat")


def build_auth_header(token: str) -> str:
    """允许直接粘贴完整的 Authorization 值，也允许只粘贴 token。"""
    token = token.strip()
    return token if " " in token else f"Cloud-IDE-JWT {token}"


def post(url: str, auth: str) -> tuple[int, str]:
    req = urllib.request.Request(
        url,
        data=b"{}",
        headers={"Authorization": auth, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.status, resp.read().decode("utf-8", "replace")


def is_already_checked(body: str) -> bool:
    text = body.lower()
    if any(hint in text for hint in CHECKED_HINTS):
        return True
    try:
        data = json.loads(body).get("data") or {}
    except (ValueError, AttributeError):
        return False
    if not isinstance(data, dict):
        return False
    return any(data.get(key) is True for key in CHECKED_KEYS)


def main() -> int:
    token = os.environ.get("TRAE_TOKEN", "")
    if not token.strip():
        print(
            "缺少环境变量 TRAE_TOKEN，请在仓库 Settings -> Secrets and variables -> Actions 中配置",
            file=sys.stderr,
        )
        return 1

    auth = build_auth_header(token)

    try:
        status, body = post(STATUS_URL, auth)
    except urllib.error.HTTPError as exc:
        print(f"查询签到状态失败：HTTP {exc.code} {exc.read().decode('utf-8', 'replace')}", file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(f"查询签到状态失败：{exc.reason}", file=sys.stderr)
        return 1

    print(f"[status] HTTP {status} {body}")

    if is_already_checked(body):
        print("今日已签到，无需重复领取")
        return 0

    try:
        status, body = post(CLAIM_URL, auth)
    except urllib.error.HTTPError as exc:
        print(f"领取积分失败：HTTP {exc.code} {exc.read().decode('utf-8', 'replace')}", file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(f"领取积分失败：{exc.reason}", file=sys.stderr)
        return 1

    print(f"[claim] HTTP {status} {body}")
    print("签到完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
