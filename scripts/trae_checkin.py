#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TraeCode 每日签到领取积分。

依赖环境变量 TRAE_TOKEN 和 TRAE_DEVICE_ID，取值方式：在本机运行
`python scripts/trae_token.py` 从客户端登录态中解出，然后填入 GitHub Secret。
"""

import json
import os
import sys
import urllib.error
import urllib.request

BASE_URL = "https://api.trae.cn/trae/api/v2/ug/checkin_credits"
STATUS_URL = f"{BASE_URL}/status"
CLAIM_URL = f"{BASE_URL}/claim"

# 客户端对 TraeCode 固定传 1（TraeWork 为 2）
REQ_SOURCE = 1


def build_auth_header(token: str) -> str:
    """允许直接粘贴完整的 Authorization 值，也允许只粘贴 token 本身。"""
    token = token.strip()
    return token if " " in token else f"Cloud-IDE-JWT {token}"


def post(url: str, auth: str, device_id: str) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps({"req_source": REQ_SOURCE}).encode(),
        headers={
            "Authorization": auth,
            "Content-Type": "application/json",
            # 缺少 x-device-id 时服务端会返回 9004
            "x-device-id": device_id,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    token = os.environ.get("TRAE_TOKEN", "")
    device_id = os.environ.get("TRAE_DEVICE_ID", "").strip()
    if not token.strip() or not device_id:
        print(
            "缺少 TRAE_TOKEN 或 TRAE_DEVICE_ID，请先运行 python scripts/trae_token.py 获取后写入 Secret",
            file=sys.stderr,
        )
        return 1

    auth = build_auth_header(token)

    try:
        status = post(STATUS_URL, auth, device_id)
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
        claim = post(CLAIM_URL, auth, device_id)
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
