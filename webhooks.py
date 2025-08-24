import logging
import aiohttp
import asyncio
from typing import Dict, Any, List
from datetime import datetime

from config import Config

logger = logging.getLogger(__name__)

class WebhookSystem:
    def __init__(self):
        self.webhooks = []
        self.session = None
    
    async def init(self):
        self.session = aiohttp.ClientSession()
        logger.info("Webhook system initialized")
    
    async def close(self):
        if self.session:
            await self.session.close()
        logger.info("Webhook system closed")
    
    def add_webhook(self, url: str, secret: str, events: List[str]):
        self.webhooks.append({
            'url': url,
            'secret': secret,
            'events': events
        })
        logger.info(f"Webhook added: {url}")
    
    async def send_webhook(self, event_type: str, data: Dict[str, Any]):
        if not self.webhooks:
            return
        
        payload = {
            'event_type': event_type,
            'data': data,
            'timestamp': datetime.now().isoformat(),
            'bot_id': Config.BOT_TOKEN.split(':')[0]
        }
        
        for webhook in self.webhooks:
            if event_type in webhook['events']:
                try:
                    headers = {
                        'Content-Type': 'application/json',
                        'X-Webhook-Secret': webhook['secret'],
                        'X-Webhook-Event': event_type
                    }
                    
                    async with self.session.post(webhook['url'], json=payload, headers=headers) as response:
                        if response.status == 200:
                            logger.info(f"Webhook sent to {webhook['url']} for event {event_type}")
                        else:
                            logger.warning(f"Webhook failed: {response.status} for {webhook['url']}")
                
                except Exception as e:
                    logger.error(f"Webhook error for {webhook['url']}: {e}")
    
    async def on_message_received(self, message_data: Dict[str, Any]):
        await self.send_webhook('message.received', message_data)
    
    async def on_message_moderated(self, message_data: Dict[str, Any], approved: bool):
        event_data = {
            'message': message_data,
            'approved': approved,
            'moderated_at': datetime.now().isoformat()
        }
        await self.send_webhook('message.moderated', event_data)
    
    async def on_punishment_created(self, punishment_data: Dict[str, Any]):
        await self.send_webhook('punishment.created', punishment_data)
    
    async def on_punishment_expired(self, punishment_data: Dict[str, Any]):
        await self.send_webhook('punishment.expired', punishment_data)
    
    async def on_user_created(self, user_data: Dict[str, Any]):
        await self.send_webhook('user.created', user_data)
    
    async def on_error_occurred(self, error_data: Dict[str, Any]):
        await self.send_webhook('error.occurred', error_data)

webhook_system = WebhookSystem()