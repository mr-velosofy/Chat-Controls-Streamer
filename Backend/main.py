# backend/main.py
import os
import asyncio
import json
from typing import Dict, Optional, Any
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorClient
from uuid import uuid4
from datetime import datetime

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "remote_keypress")

mongo = AsyncIOMotorClient(MONGO_URI, tls=True, tlsAllowInvalidCertificates=False)
db = mongo[DB_NAME]
users_col = db["users"]

app = FastAPI(title="Remote Keypress Backend (token->uuid, keys saved on each login)")

# In-memory map of uuid -> websocket (live connections)
connections: Dict[str, WebSocket] = {}

class WSInit(BaseModel):
    access_token: str
    keys: Optional[list] = None  # array of {action_name, keybind, duration}

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    try:
        # Expect the first incoming JSON message to contain access_token + keys
        data = await ws.receive_text()
        try:
            payload = json.loads(data)
        except Exception:
            await ws.close(code=4000)
            return

        if "access_token" not in payload:
            await ws.close(code=4001)
            return

        access_token = payload["access_token"]
        keys = payload.get("keys", [])

        # Find user by access_token or create one
        user = await users_col.find_one({"access_token": access_token})
        if user is None:
            # create new user with stable uuid
            user_uuid = str(uuid4())
            user_doc = {
                "access_token": access_token,
                "uuid": user_uuid,
                "keys": keys,
                "created_at": datetime.now(),
                "last_seen": datetime.now(),
            }
            await users_col.insert_one(user_doc)
        # elif no uuid is there but user is then give them one and add the keybinds
        elif "uuid" not in user:
            user_uuid = str(uuid4())
            await users_col.update_one(
                {"access_token": access_token},
                {"$set": {"uuid": user_uuid, "keys": keys}}
            )
        else:
            user_uuid = user["uuid"]
            # upsert keys & last_seen on every login/connect
            await users_col.update_one(
                {"access_token": access_token},
                {"$set": {"keys": keys, "last_seen": datetime.now()}}
            )

        # register connection
        connections[user_uuid] = ws
        print(f"[WS] connected uuid={user_uuid} keys_count={len(keys)}")

        # keep listening — simple echo/ping or wait to detect disconnect
        while True:
            # We don't need client messages, but receive_text will wait; use small timeout via asyncio.wait_for if desired
            try:
                msg = await ws.receive_text()
                # optional: handle pings from client
            except WebSocketDisconnect:
                break
            except Exception:
                # client might send binary or close — handle gracefully
                break

    except Exception as e:
        print("ws error:", e)
    finally:
        # cleanup: remove connection if present
        # note: multiple clients for same uuid not supported in this simple design
        for u, conn in list(connections.items()):
            if conn is ws:
                connections.pop(u, None)
                print(f"[WS] disconnected uuid={u}")
                break
        try:
            await ws.close()
        except Exception:
            pass

@app.get("/endpoint/{uuid}/{action_name}")
async def trigger_action(uuid: str, action_name: str, request: Request):
    user_name = None
    try:
        user = request.headers.get("Nightbot-User")
        # user is a str in FastAPI so use split to find displayName
        user_name = user.split("displayName=")[1].split("&")[0]
        print(f"Action triggered by Nightbot user: {user_name}")
    except:
        pass # ignore if header not present or malformed
    
    await asyncio.sleep(2)  # small delay to simulate processing
    # Find user and keys from DB
    user = await users_col.find_one({"uuid": uuid})
    if not user:
        raise HTTPException(status_code=404, detail="uuid not found")

    keys = user.get("keys", []) or []
    action = next((k for k in keys if k.get("action_name").lower() == action_name.lower()), None)
    if not action:
        return JSONResponse({"error": "action not available"}, status_code=400)

    # If client is connected, send action via websocket
    ws = connections.get(uuid)
    if not ws:
        return JSONResponse({"error": "client not connected"}, status_code=400)

    try:
        await ws.send_text(json.dumps({"action": action, "user_name": user_name}))
        return {"status": "sent", "uuid": uuid, "action": action}
    except Exception as e:
        return JSONResponse({"error": "failed to deliver", "detail": str(e)}, status_code=500)

@app.get("/whoami/{access_token}")
async def whoami(access_token: str):
    # convenience: quickly find uuid for a given token
    user = await users_col.find_one({"access_token": access_token})
    if not user:
        raise JSONResponse({"error": "token not registered"}, status_code=404)
    return {"uuid": user["uuid"], "keys": user.get("keys", [])}

@app.get("/healthz")
async def healthz():
    return {"ok": True}
