import logging
from fastapi import FastAPI, HTTPException, Security, Depends
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import datetime
import uvicorn

from config import Config
from storage import user_levels, moderator_stats, punishments, active_punishments, init_punishment_system
from handlers import send_moderation_log, send_punishment_log

logger = logging.getLogger(__name__)

class UserResponse(BaseModel):
    user_id: int
    level: int
    username: Optional[str] = None

class ModStatsResponse(BaseModel):
    moderator_id: int
    approved: int
    rejected: int
    reviewed: int
    warnings: int

class PunishmentRequest(BaseModel):
    user_id: int
    punishment_type: str
    duration: Optional[int] = None
    reason: str

class PunishmentResponse(BaseModel):
    user_id: int
    type: str
    duration: int
    reason: str
    moderator_id: int
    created_at: str
    expires_at: str

class WebhookEvent(BaseModel):
    event_type: str
    data: dict
    timestamp: str

app = FastAPI(title="Anonymous Bot API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_key_header = APIKeyHeader(name="X-API-Key")

async def get_api_key(api_key: str = Security(api_key_header)):
    if api_key != Config.API_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key

@app.get("/")
async def root():
    return {"message": "Anonymous Bot API", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.datetime.now().isoformat()}

@app.get("/users", response_model=List[UserResponse])
async def get_users(api_key: str = Depends(get_api_key)):
    users = []
    for user_id, level in user_levels.items():
        users.append(UserResponse(user_id=user_id, level=level))
    return users

@app.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, api_key: str = Depends(get_api_key)):
    level = user_levels.get(user_id, 0)
    return UserResponse(user_id=user_id, level=level)

@app.post("/users/{user_id}/level")
async def set_user_level(user_id: int, level: int, api_key: str = Depends(get_api_key)):
    if level not in [0, 1, 2, 3]:
        raise HTTPException(status_code=400, detail="Level must be between 0 and 3")
    
    user_levels.set(user_id, level)
    return {"message": f"User {user_id} level set to {level}"}

@app.get("/moderators/stats", response_model=List[ModStatsResponse])
async def get_moderators_stats(api_key: str = Depends(get_api_key)):
    stats = []
    for mod_id, mod_stats in moderator_stats.items():
        stats.append(ModStatsResponse(
            moderator_id=mod_id,
            approved=mod_stats.get('approved', 0),
            rejected=mod_stats.get('rejected', 0),
            reviewed=mod_stats.get('reviewed', 0),
            warnings=mod_stats.get('warnings', 0)
        ))
    return stats

@app.post("/punishments")
async def create_punishment(punishment: PunishmentRequest, api_key: str = Depends(get_api_key)):
    from storage import Punishment
    from config import Config
    
    if punishment.punishment_type not in ['mute', 'warning', 'ban']:
        raise HTTPException(status_code=400, detail="Invalid punishment type")
    
    duration = punishment.duration or {
        'mute': Config.DEFAULT_MUTE_DURATION,
        'ban': Config.DEFAULT_BAN_DURATION,
        'warning': 0
    }[punishment.punishment_type]
    
    new_punishment = Punishment(
        user_id=punishment.user_id,
        punishment_type=punishment.punishment_type,
        duration=duration,
        reason=punishment.reason,
        moderator_id=0
    )
    
    from main import punishment_system
    await punishment_system.add_punishment(new_punishment)
    
    await send_punishment_log(
        "API System", 0, f"user_{punishment.user_id}", 
        punishment.user_id, punishment.punishment_type, punishment.reason
    )
    
    return {"message": "Punishment created", "punishment_id": punishment.user_id}

@app.get("/punishments/active", response_model=List[PunishmentResponse])
async def get_active_punishments(api_key: str = Depends(get_api_key)):
    active = []
    for user_id, punishment in active_punishments.items():
        active.append(PunishmentResponse(**punishment.to_dict()))
    return active

@app.delete("/punishments/{user_id}")
async def remove_punishment(user_id: int, api_key: str = Depends(get_api_key)):
    from main import punishment_system
    await punishment_system.remove_punishment(user_id)
    return {"message": f"Punishment removed for user {user_id}"}

@app.post("/webhook/event")
async def receive_webhook(event: WebhookEvent, api_key: str = Depends(get_api_key)):
    logger.info(f"Webhook received: {event.event_type}")
    return {"message": "Webhook received"}

@app.post("/webhook/send")
async def send_webhook(event_type: str, data: dict, api_key: str = Depends(get_api_key)):
    logger.info(f"Webhook sent: {event_type}")
    return {"message": "Webhook sent"}

def start_api_server():
    uvicorn.run(app, host=Config.API_HOST, port=Config.API_PORT)