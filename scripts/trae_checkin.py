#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TraeCode 每日签到领取积分。

两种取用凭证的方式，优先用第一种：

1. TRAE_COOKIE：浏览器登录 trae.cn 后的 Cookie。
   脚本每天用它调 GetUserToken 换一把新的 Cloud-IDE-JWT，不会过期。
2. TRAE_TOKEN：直接给出的 Cloud-IDE-JWT（约 14 天失效，作为兜底）。

两者都需要 TRAE_DEVICE_ID，取值方式见 scripts/trae_token.py。
"""

import json
import os
import sys
import urllib.error
import urllib.request

TOKEN_URL = "https://api.trae.cn/cloudide/api/v3/common/GetUserToken"
BASE_URL = "https://api.trae.cn/trae/api/v2/ug/checkin_credits"
STATUS_URL = f"{BASE_URL}/status"
CLAIM_URL = f"{BASE_URL}/claim"

# 客户端对 TraeCode 固定传 1（TraeWork 为 2）
REQ_SOURCE = 1


def mint_token(cookie: str) -> str:
    """用网站 Cookie 换一把新的 Cloud-IDE-JWT，失败返回空串。"""
    req = urllib.request.Request(
        TOKEN_URL,
        data=b"{}",
        headers={"Content-Type": "application/json", "Cookie": cookie},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8")).get("Result") or {}
    except (urllib.error.HTTPError, urllib.error.URLError, ValueError) as exc:
        print(f"Cookie 换取 token 失败（将回退到 TRAE_TOKEN）：{exc}", file=sys.stderr)
        return ""

    token = result.get("Token", "")
    if token:
        print(f"已用 Cookie 换取新 token，有效期至 {result.get('ExpiredAt', '(未返回)')}")
    return token


def post_checkin(url: str, token: str, device_id: str) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps({"req_source": REQ_SOURCE}).encode(),
        headers={
            "Authorization": f"Cloud-IDE-JWT {token}",
            "Content-Type": "application/json",
            # 缺少 x-device-id 时服务端会返回 9004
            "x-device-id": device_id,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    cookie = os.environ.get("TRAE_COOKIE", "").strip()
    device_id = os.environ.get("TRAE_DEVICE_ID", "").strip()

    if not device_id:
        print("缺少 TRAE_DEVICE_ID，请运行 python scripts/trae_token.py 获取", file=sys.stderr)
        return 1

    token = mint_token(cookie) if cookie else ""
    if not token:
        token = os.environ.get("TRAE_TOKEN", "").strip()
    if not token:
        print("TRAE_COOKIE 与 TRAE_TOKEN 都不可用，无法签到", file=sys.stderr)
        return 1

    try:
        status = post_checkin(STATUS_URL, token, device_id)
    except urllib.error.HTTPError as exc:
        print(f"查询签到状态失败：HTTP {exc.code} {exc.read().decode('utf-8', 'replace')}", file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(f"查询签到状态失败：{exc.reason}", file=sys.stderr)
        return 1

    print(f"[status] {json.dumps(status, ensure_ascii=False)}")

    if status.get("checked_in"):
        print(f"今日已签到，当前积分：{status.get('credits')}")
        return 0

    if not status.get("enable"):
        print("当前账号未开放签到，跳过")
        return 0

    try:
        claim = post_checkin(CLAIM_URL, token, device_id)
    except urllib.error.HTTPError as exc:
        print(f"领取积分失败：HTTP {exc.code} {exc.read().decode('utf-8', 'replace')}", file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(f"领取积分失败：{exc.reason}", file=sys.stderr)
        return 1

    print(f"[claim] {json.dumps(claim, ensure_ascii=False)}")

    if claim.get("code") == 0:
        credits = (claim.get("data") or {}).get("credits")
        print(f"签到成功，获得积分：{credits}")
        return 0

    print(f"签到失败：{claim.get('message') or claim}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
