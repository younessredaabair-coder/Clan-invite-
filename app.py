# -*- coding: utf-8 -*-
import base64
import json
from collections import OrderedDict
from datetime import datetime
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from flask import Flask, Response, jsonify, request
import requests
import urllib3

import QuitClanReq_pb2
import ReqCLan_pb2

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
app = Flask(__name__)

OB = "OB55"

API_INFO = {
    "developer": "RIZER",
    "telegram": "@Beotherjk",
    "api_name": "FF GUILD JOIN/LEAVE API",
    "version": OB
}

# Crypto keys
KEY = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56])
IV = bytes([54, 111, 121, 90, 68, 114, 50, 50, 69, 51, 121, 99, 104, 106, 77, 37])

GAME_HEADERS = {
    "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 12; SM-G998B)",
    "Connection": "Keep-Alive",
    "Accept-Encoding": "gzip",
    "Content-Type": "application/x-www-form-urlencoded",
    "X-Unity-Version": "2018.4.11f1",
    "X-GA": "v1 1",
    "ReleaseVersion": OB,
    "Expect": "100-continue"
}

# ==================== Helpers ====================
def encrypt_payload(data: bytes) -> bytes:
    cipher = AES.new(KEY, AES.MODE_CBC, IV)
    return cipher.encrypt(pad(data, AES.block_size))

def decode_jwt(token: str):
    """Extract account_id, nickname, region directly from JWT payload"""
    try:
        parts = token.split(".")
        if len(parts) >= 2:
            padded = parts[1] + "=" * (-len(parts[1]) % 4)
            payload = json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
            account_id = str(payload.get("account_id"))
            nickname = payload.get("nickname", "Unknown")
            lock_region = payload.get("lock_region") or payload.get("noti_region") or "ME"
            return account_id, nickname, lock_region
    except Exception:
        pass
    return None, None, None

def extract_jwt_from_response(data):
    """Recursively search for a valid JWT string"""
    if isinstance(data, str):
        cleaned = data.strip().strip('"').strip("'")
        if cleaned.startswith("ey") and cleaned.count(".") == 2:
            return cleaned
    elif isinstance(data, dict):
        for k in ["jwt", "token", "jwt_token", "game_token", "access_token"]:
            val = data.get(k)
            if isinstance(val, str) and val.startswith("ey") and val.count(".") == 2:
                return val
        for v in data.values():
            found = extract_jwt_from_response(v)
            if found:
                return found
    elif isinstance(data, list):
        for item in data:
            found = extract_jwt_from_response(item)
            if found:
                return found
    return None

# ==================== JWT Generation via Lovable API ====================
def get_jwt_from_lovable_api(uid: str, password: str):
    url = f"https://ff-jwt-gen-api.lovable.app/api/public/token?uid={uid.strip()}&password={password.strip()}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/json"
    }
    try:
        r = requests.get(url, headers=headers, timeout=15)
        try:
            jwt_token = extract_jwt_from_response(r.json())
            if jwt_token:
                return jwt_token
        except Exception:
            jwt_token = extract_jwt_from_response(r.text)
            if jwt_token:
                return jwt_token
    except Exception as e:
        print(f"[-] Lovable API error: {e}")
    return None

def get_jwt_from_access_token(access_token: str):
    try:
        url = f"https://rizerxaccessjwt.vercel.app/rizer?access_token={access_token.strip()}"
        r = requests.get(url, timeout=8)
        if r.status_code == 200:
            data = r.json()
            if data.get("success") and "jwt" in data:
                return data["jwt"]
    except Exception:
        pass
    return None

# ==================== Clan Actions ====================
def request_clan(jwt_token: str, clan_id: int, region: str):
    msg = ReqCLan_pb2.MyMessage()
    msg.field_1 = int(clan_id)
    payload = encrypt_payload(msg.SerializeToString())

    headers = GAME_HEADERS.copy()
    headers["Authorization"] = f"Bearer {jwt_token}"

    # سيرفرات Free Fire الحالية النشطة لطلبات الكلان
    gateways = [
        "https://clientbp.ggpolarbear.com/RequestJoinClan",
        "https://clientbp.common.ggbluefox.com/RequestJoinClan",
        "https://clientbp.ggwhitehawk.com/RequestJoinClan",
        "https://clientbp.ggblueshark.com/RequestJoinClan",
        "https://client.ind.freefiremobile.com/RequestJoinClan"
    ]

    last_error = ""
    for url in gateways:
        try:
            print(f"[*] Trying Clan Gateway: {url}")
            r = requests.post(url, headers=headers, data=payload, verify=False, timeout=10)
            print(f"    -> Status: {r.status_code} | Response: {r.text[:100]}")

            # إذا استجاب السيرفر بنجاح أو بكود خطأ منطقي (مثل الحساب في كلان مسبقاً)
            if r.status_code in [200, 400]:
                return r.status_code, r.text
        except requests.exceptions.RequestException as e:
            print(f"    -> Gateway failed: {e}")
            last_error = str(e)
            continue

    return 500, f"Gateway connection error: {last_error}"

def quit_clan(jwt_token: str, clan_id: int, region: str):
    msg = QuitClanReq_pb2.QuitClanReq()
    msg.field_1 = int(clan_id)
    payload = encrypt_payload(msg.SerializeToString())

    headers = GAME_HEADERS.copy()
    headers["Authorization"] = f"Bearer {jwt_token}"

    gateways = [
        "https://clientbp.ggpolarbear.com/QuitClan",
        "https://clientbp.common.ggbluefox.com/QuitClan",
        "https://clientbp.ggwhitehawk.com/QuitClan",
        "https://clientbp.ggblueshark.com/QuitClan",
        "https://client.ind.freefiremobile.com/QuitClan"
    ]

    last_error = ""
    for url in gateways:
        try:
            print(f"[*] Trying Quit Gateway: {url}")
            r = requests.post(url, headers=headers, data=payload, verify=False, timeout=10)
            print(f"    -> Status: {r.status_code} | Response: {r.text[:100]}")

            if r.status_code in [200, 400]:
                return r.status_code, r.text
        except requests.exceptions.RequestException as e:
            last_error = str(e)
            continue

    return 500, f"Gateway connection error: {last_error}"

# ==================== Login Resolver ====================
def resolve_login(jwt_token=None, uid=None, password=None, access_token=None):
    # 1. Direct JWT
    if jwt_token:
        acc_id, name, region = decode_jwt(jwt_token)
        if acc_id:
            return jwt_token, acc_id, name, region, "JWT"
        return None, None, None, None, "Invalid JWT"

    # 2. UID + Password via Lovable API
    if uid and password:
        jwt_token = get_jwt_from_lovable_api(uid, password)
        if jwt_token:
            acc_id, name, region = decode_jwt(jwt_token)
            return jwt_token, acc_id, name, region, "LOVABLE_API_UID_PASS"
        return None, None, None, None, "Failed to generate JWT via Lovable API"

    # 3. Access Token
    if access_token:
        jwt_token = get_jwt_from_access_token(access_token)
        if jwt_token:
            acc_id, name, region = decode_jwt(jwt_token)
            return jwt_token, acc_id, name, region, "ACCESS_TOKEN"
        return None, None, None, None, "Access token conversion failed"

    return None, None, None, None, "No login credentials provided"

def get_param(key, default=None):
    val = request.args.get(key)
    if val is None and request.is_json:
        val = request.json.get(key)
    return val if val is not None else default

# ==================== Endpoints ====================
@app.route("/")
def home():
    data = OrderedDict()
    data["success"] = True
    data["message"] = f"Free Fire Clan API ({OB})"
    data["version"] = OB
    data["auth_provider"] = "ff-jwt-gen-api.lovable.app"
    data["examples"] = {
        "request_clan_uidpass": "/request_clan?clan_id=3105390852&uid=7885349591&pass=ZED-JULIANT5C0EG",
        "request_clan_jwt": "/request_clan?clan_id=3105390852&jwt=JWT_TOKEN",
        "quit_clan_uidpass": "/quit_clan?clan_id=3105390852&uid=7885349591&pass=ZED-JULIANT5C0EG"
    }
    return Response(json.dumps(data, indent=2), mimetype="application/json")

@app.route("/request_clan", methods=["GET", "POST"])
def api_request_clan():
    clan_id = get_param("clan_id")
    jwt_token = get_param("jwt")
    uid = get_param("uid")
    password = get_param("pass") or get_param("password")

    if not clan_id:
        return jsonify({"success": False, "error": "clan_id is required"}), 400

    final_jwt, acc_id, name, region, method = resolve_login(
        jwt_token=jwt_token, uid=uid, password=password
    )

    if not final_jwt:
        return jsonify({"success": False, "error": method}), 400

    code, text = request_clan(final_jwt, clan_id, region)
    return jsonify({
        "success": (code == 200),
        "action": "Join Clan",
        "clan_id": clan_id,
        "uid": acc_id,
        "name": name,
        "region": region,
        "login_method": method,
        "api_version": OB,
        "status_code": code,
        "server_response": text
    })

@app.route("/quit_clan", methods=["GET", "POST"])
def api_quit_clan():
    clan_id = get_param("clan_id")
    jwt_token = get_param("jwt")
    uid = get_param("uid")
    password = get_param("pass") or get_param("password")

    if not clan_id:
        return jsonify({"success": False, "error": "clan_id required"}), 400

    final_jwt, acc_id, name, region, method = resolve_login(
        jwt_token=jwt_token, uid=uid, password=password
    )

    if not final_jwt:
        return jsonify({"success": False, "error": method}), 400

    code, text = quit_clan(final_jwt, clan_id, region)
    return jsonify({
        "success": (code == 200),
        "action": "Quit Clan",
        "clan_id": clan_id,
        "uid": acc_id,
        "name": name,
        "region": region,
        "login_method": method,
        "api_version": OB,
        "status_code": code,
        "server_response": text
    })

@app.route("/request_clan_access", methods=["GET", "POST"])
def api_request_access():
    clan_id = get_param("clan_id")
    access_token = get_param("access_token")

    if not clan_id or not access_token:
        return jsonify({"success": False, "error": "clan_id and access_token required"}), 400

    final_jwt, acc_id, name, region, method = resolve_login(access_token=access_token)
    if not final_jwt:
        return jsonify({"success": False, "error": method}), 400

    code, text = request_clan(final_jwt, clan_id, region)
    return jsonify({
        "success": (code == 200),
        "action": "Join Clan",
        "clan_id": clan_id,
        "uid": acc_id,
        "name": name,
        "region": region,
        "login_method": method,
        "api_version": OB,
        "status_code": code,
        "server_response": text
    })

@app.route("/quit_clan_access", methods=["GET", "POST"])
def api_quit_access():
    clan_id = get_param("clan_id")
    access_token = get_param("access_token")

    if not clan_id or not access_token:
        return jsonify({"success": False, "error": "clan_id and access_token required"}), 400

    final_jwt, acc_id, name, region, method = resolve_login(access_token=access_token)
    if not final_jwt:
        return jsonify({"success": False, "error": method}), 400

    code, text = quit_clan(final_jwt, clan_id, region)
    return jsonify({
        "success": (code == 200),
        "action": "Quit Clan",
        "clan_id": clan_id,
        "uid": acc_id,
        "name": name,
        "region": region,
        "login_method": method,
        "api_version": OB,
        "status_code": code,
        "server_response": text
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)