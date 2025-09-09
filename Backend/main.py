import os
import asyncio
import json
from typing import Dict, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorClient
from uuid import uuid4
from datetime import datetime
from dotenv import load_dotenv
import certifi
from contextlib import asynccontextmanager

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "remote_keypress")

# Globals to be set during lifespan
mongo: AsyncIOMotorClient | None = None
users_col = None
connections: Dict[str, WebSocket] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    global mongo, users_col
    # Initialize MongoDB based on connection URI
    if MONGO_URI.startswith("mongodb+srv://"):
        mongo = AsyncIOMotorClient(MONGO_URI, tls=True, tlsCAFile=certifi.where())
    else:
        mongo = AsyncIOMotorClient(MONGO_URI)

    try:
        await mongo.admin.command("ping")
        print(f"✅ MongoDB connected: {DB_NAME} at {MONGO_URI}")
    except Exception as e:
        print(f"⛔ MongoDB connection failed: {e}")
        # Send startup_failed to ASGI server by re-raising
        raise

    db = mongo[DB_NAME]
    users_col = db["users"]

    yield  # ASGI signals "lifespan.startup.complete" here

    mongo.close()
    print("🛑 MongoDB connection closed")


app = FastAPI(
    title="Remote Keypress Backend",
    lifespan=lifespan,
)

class WSInit(BaseModel):
    access_token: str
    keys: Optional[list] = None


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    try:
        data = await ws.receive_text()
        payload = json.loads(data)
        access_token = payload.get("access_token")
        if not access_token:
            await ws.close(code=4001)
            return
        keys = payload.get("keys", [])

        user = await users_col.find_one({"access_token": access_token})
        if user is None:
            user_uuid = str(uuid4())
            user_doc = {
                "access_token": access_token,
                "uuid": user_uuid,
                "keys": keys,
                "created_at": datetime.now(),
                "last_seen": datetime.now(),
            }
            await users_col.insert_one(user_doc)
        elif "uuid" not in user:
            user_uuid = str(uuid4())
            await users_col.update_one({"access_token": access_token},
                                       {"$set": {"uuid": user_uuid, "keys": keys}})
        else:
            user_uuid = user["uuid"]
            await users_col.update_one({"access_token": access_token},
                                       {"$set": {"keys": keys, "last_seen": datetime.now()}})

        connections[user_uuid] = ws
        print(f"[WS] Connected uuid={user_uuid} keys={len(keys)}")

        while True:
            try:
                await ws.receive_text()
            except WebSocketDisconnect:
                break
            except Exception:
                break

    except Exception as e:
        print("WS error:", e)
    finally:
        for u, conn in list(connections.items()):
            if conn is ws:
                connections.pop(u, None)
                print(f"[WS] Disconnected uuid={u}")
                break
        try:
            await ws.close()
        except:
            pass


@app.get("/endpoint/{uuid}/{action_name}")
async def trigger_action(uuid: str, action_name: str, request: Request):
    user_name = None
    try:
        nh = request.headers.get("Nightbot-User")
        user_name = nh.split("displayName=")[1].split("&")[0] if nh else None
        if user_name:
            print(f"Action triggered by Nightbot user: {user_name}")
    except Exception:
        pass

    await asyncio.sleep(2)

    user = await users_col.find_one({"uuid": uuid})
    if not user:
        raise HTTPException(status_code=404, detail="uuid not found")

    action = next((k for k in (user.get("keys") or [])
                   if k.get("action_name", "").lower() == action_name.lower()), None)
    if not action:
        return JSONResponse({"error": "action not available"}, status_code=400)

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
    user = await users_col.find_one({"access_token": access_token})
    if not user:
        raise HTTPException(status_code=404, detail="token not registered")
    return {"uuid": user["uuid"], "keys": user.get("keys", [])}


@app.get("/healthz")
async def healthz():
    return {"ok": True}
