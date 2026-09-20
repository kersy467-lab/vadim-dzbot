from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, List
import json
import time

multiplayer_hub_router = APIRouter(prefix="/ws/multiplayer", tags=["RPG Multiplayer"])

class WorldRoshanThreatEngine:
    def __init__(self):
        self.hp = 2800000
        self.max_hp = 2800000
        self.phase = 1
        self.enrage = 1.0
        self.active_telegraph = None

    def update(self):
        # Simulated Boss AI Loop
        if self.hp < self.max_hp * 0.5 and self.phase == 1:
            self.phase = 2
            self.enrage = 1.42
            self.active_telegraph = {
                "name": "ROSHAN_SLAM",
                "x": 500, "y": 400,
                "radius": 280,
                "remainingTime": 1.2
            }
        
    def get_state(self):
        return {
            "hp": self.hp,
            "maxHp": self.max_hp,
            "phase": self.phase,
            "enrageMultiplier": self.enrage,
            "activeTelegraph": self.active_telegraph
        }

class RoomManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.room_states: Dict[str, dict] = {}
        self.roshan = WorldRoshanThreatEngine()

    async def connect(self, room_id: str, websocket: WebSocket):
        await websocket.accept()
        if room_id not in self.active_connections:
            self.active_connections[room_id] = []
            self.room_states[room_id] = {"players": {}}
        self.active_connections[room_id].append(websocket)

    def disconnect(self, room_id: str, websocket: WebSocket):
        if room_id in self.active_connections:
            self.active_connections[room_id].remove(websocket)
            if not self.active_connections[room_id]:
                del self.active_connections[room_id]
                del self.room_states[room_id]

    async def broadcast(self, room_id: str, message: dict):
        if room_id in self.active_connections:
            for connection in self.active_connections[room_id]:
                try:
                    await connection.send_json(message)
                except:
                    pass

manager = RoomManager()

@multiplayer_hub_router.websocket("/{room_id}")
async def multiplayer_endpoint(websocket: WebSocket, room_id: str):
    await manager.connect(room_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            # Threat Engine & 60Hz Sync (Simulated)
            if data.get("type") == "PLAYER_INPUT":
                p_id = data.get("id", "unknown")
                if room_id in manager.room_states:
                    manager.room_states[room_id]["players"][p_id] = {
                        "id": p_id,
                        "x": data.get("x", 450),
                        "y": data.get("y", 320),
                        "anim": "ATTACK" if data.get("attack") else "IDLE",
                        "hp": data.get("hp", 1000),
                        "mp": data.get("mp", 500)
                    }
                
                manager.roshan.update()
                
                state_packet = {
                    "type": "ROOM_STATE",
                    "tick": data.get("tick", 0),
                    "players": list(manager.room_states.get(room_id, {}).get("players", {}).values()),
                    "boss": manager.roshan.get_state(),
                    "projectiles": [],
                    "floatingTexts": []
                }
                await manager.broadcast(room_id, state_packet)
            else:
                await manager.broadcast(room_id, data)
    except WebSocketDisconnect:
        manager.disconnect(room_id, websocket)
