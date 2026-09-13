"""微信服务端接口封装：code2Session、内容安全、小程序码。WX_MOCK=true 时全部本地模拟。"""

import time

import httpx

from app.config import settings

_token_cache: dict = {"value": None, "expires": 0}

SENSITIVE_WORDS = ["傻逼", "去死", "杀了", "诈骗犯", "全家"]


class WeChatError(Exception):
    pass


async def code2session(code: str) -> dict:
    if settings.wx_mock:
        return {"openid": f"mock_{code}", "unionid": None}
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            "https://api.weixin.qq.com/sns/jscode2session",
            params={
                "appid": settings.wx_appid,
                "secret": settings.wx_secret,
                "js_code": code,
                "grant_type": "authorization_code",
            },
        )
    data = r.json()
    if "openid" not in data:
        raise WeChatError(data.get("errmsg", "code2session failed"))
    return data


async def _access_token() -> str:
    if _token_cache["value"] and _token_cache["expires"] > time.time() + 60:
        return _token_cache["value"]
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            "https://api.weixin.qq.com/cgi-bin/token",
            params={"grant_type": "client_credential", "appid": settings.wx_appid, "secret": settings.wx_secret},
        )
    data = r.json()
    if "access_token" not in data:
        raise WeChatError(data.get("errmsg", "get token failed"))
    _token_cache["value"] = data["access_token"]
    _token_cache["expires"] = time.time() + data.get("expires_in", 7200)
    return data["access_token"]


def local_sensitive_check(text: str) -> bool:
    return not any(w in text for w in SENSITIVE_WORDS)


async def msg_sec_check(text: str, openid: str, scene: int = 2) -> bool:
    """返回 True 表示通过。先过本地敏感词，再调微信 msgSecCheck 2.0。"""
    if not local_sensitive_check(text):
        return False
    if settings.wx_mock:
        return True
    token = await _access_token()
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(
            f"https://api.weixin.qq.com/wxa/msg_sec_check?access_token={token}",
            json={"content": text, "version": 2, "scene": scene, "openid": openid},
        )
    data = r.json()
    return data.get("errcode") == 0 and data.get("result", {}).get("suggest") == "pass"


async def get_unlimited_qrcode(scene: str, page: str) -> bytes | None:
    if settings.wx_mock:
        return None
    token = await _access_token()
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(
            f"https://api.weixin.qq.com/wxa/getwxacodeunlimit?access_token={token}",
            json={"scene": scene, "page": page, "width": 280, "check_path": False},
        )
    if r.headers.get("content-type", "").startswith("image"):
        return r.content
    return None
