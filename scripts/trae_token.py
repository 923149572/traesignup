#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从本机 TraeCode 登录态中解出配置 GitHub Secret 所需的两个值。

- token：iCubeAuthInfo://icube.cloudide 字段，AES-128-CBC 加密后 base64，
  解出来是登录信息 JSON，其中的 token 即 Cloud-IDE-JWT。
- device_id：请求必须携带 x-device-id，客户端把设备号写在
  iCubeAuthInfo://icube-dc:<device_id> 这个键名里，直接取后缀即可。

用法：python scripts/trae_token.py
"""

import base64
import hashlib
import json
import os
import sys
from pathlib import Path

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

# 与客户端实现一致的布局参数
HEADER_LEN = 6       # 前 6 字节为格式头
KEY_LEN = 32         # 紧随其后的 32 字节作为密钥派生材料
PAYLOAD_OFFSET = 64  # 明文前 64 字节为校验数据，之后才是 JSON

AUTH_KEY = "iCubeAuthInfo://icube.cloudide"
DEVICE_KEY_PREFIX = "iCubeAuthInfo://icube-dc:"

_MASK_A = bytes([
    82, 9, 106, 213, 48, 54, 165, 56, 191, 64, 163, 158, 129, 243, 215, 251,
    124, 227, 57, 130, 155, 47, 255, 135, 52, 142, 67, 68, 196, 222, 233, 203,
    84, 123, 148, 50, 166, 194, 35, 61, 238, 76, 149, 11, 66, 250, 195, 78,
    8, 46, 161, 102, 40, 217, 36, 178, 118, 91, 162, 73, 109, 139, 209, 37,
])
_MASK_B = bytes([
    31, 221, 168, 51, 136, 7, 199, 49, 177, 18, 16, 89, 39, 128, 236, 95,
    96, 81, 127, 169, 25, 181, 74, 13, 45, 229, 122, 159, 147, 201, 156, 239,
    160, 224, 59, 77, 174, 42, 245, 176, 200, 235, 187, 60, 131, 83, 153, 97,
    23, 43, 4, 126, 186, 119, 214, 38, 225, 105, 20, 99, 85, 33, 12, 125,
])

STORAGE_CANDIDATES = (
    (r"Trae CN", "TraeCode"),
    (r"TRAE SOLO CN", "TraeWork"),
)


def build_mask() -> bytes:
    """_MASK_A 不足 64 字节，缺失部分按客户端行为视为 0 参与异或。"""
    return bytes(
        (_MASK_A[i] if i < len(_MASK_A) else 0) ^ _MASK_B[i]
        for i in range(len(_MASK_B))
    )


def decrypt(b64_text: str) -> str:
    blob = base64.b64decode(b64_text)
    seed = blob[HEADER_LEN:HEADER_LEN + KEY_LEN]

    material = hashlib.sha512(seed).digest() + build_mask()
    digest = hashlib.sha512(material).digest()

    aes_key = digest[:16]
    iv = digest[16:32]
    ciphertext = blob[HEADER_LEN + KEY_LEN:]

    decryptor = Cipher(algorithms.AES(aes_key), modes.CBC(iv)).decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()

    pad_len = padded[-1]
    if not 1 <= pad_len <= 16:
        raise ValueError("解密结果填充异常，登录态可能已损坏")
    return padded[:-pad_len][PAYLOAD_OFFSET:].decode("utf-8")


def find_storage() -> tuple[Path, str, dict]:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise SystemExit("未找到 APPDATA 环境变量，请在 Windows 上运行")
    for folder, product in STORAGE_CANDIDATES:
        path = Path(appdata) / folder / "User" / "globalStorage" / "storage.json"
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise SystemExit(f"读取登录态失败：{exc}") from exc
        if data.get(AUTH_KEY):
            return path, product, data
    raise SystemExit("未找到 TraeCode/TraeWork 登录态，请确认客户端已登录")


def main() -> int:
    path, product, data = find_storage()
    auth = json.loads(decrypt(data[AUTH_KEY]))

    token = auth.get("token")
    if not token:
        print("登录态中没有 token 字段，请在客户端重新登录", file=sys.stderr)
        return 1

    device_id = next(
        (key[len(DEVICE_KEY_PREFIX):] for key in data if key.startswith(DEVICE_KEY_PREFIX)),
        "",
    )
    if not device_id:
        print("未找到设备号，请先启动一次 TraeCode 客户端", file=sys.stderr)
        return 1

    print(f"# 来源：{product}  {path}")
    print("# 下面两行分别填到 GitHub 仓库的两个 Actions Secret 里")
    print(f"TRAE_TOKEN={token}")
    print(f"TRAE_DEVICE_ID={device_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
