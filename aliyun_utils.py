# aliyun_utils.py
import hashlib
import hmac
import time
from urllib.parse import quote
import httpx

def sign(access_key_id, access_key_secret, method, url, headers, body=""):
    """生成阿里云 API 签名（用于语音服务）"""
    lf = "\n"
    string_to_sign = (
        method + lf +
        (headers.get("Accept", "") or "") + lf +
        (headers.get("Content-MD5", "") or "") + lf +
        (headers.get("Content-Type", "") or "") + lf +
        (headers.get("Date", "") or "") + lf +
        _build_canonical_headers(headers) +
        url
    )
    signature = hmac.new(
        access_key_secret.encode("utf-8"),
        string_to_sign.encode("utf-8"),
        hashlib.sha1
    ).digest()
    return "acs " + access_key_id + ":" + base64.b64encode(signature).decode("utf-8")

def _build_canonical_headers(headers):
    canonical = ""
    for k in sorted(k.lower() for k in headers if k.lower().startswith("x-acs-")):
        canonical += k + ":" + str(headers[k]) + "\n"
    return canonical

import base64