import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Dict, Any, Optional

from aiokafka import AIOKafkaProducer
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC")

app = FastAPI(title="Clickstream Collector")

# Enable CORS for the website
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared producer
producer = None

@app.on_event("startup")
async def startup_event():
    global producer
    logger.info(f"Starting Kafka producer on {KAFKA_BOOTSTRAP_SERVERS}")
    producer = AIOKafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )
    await producer.start()
    logger.info("Kafka producer started")

@app.on_event("shutdown")
async def shutdown_event():
    global producer
    if producer:
        await producer.stop()
        logger.info("Kafka producer stopped")

class ClickEvent(BaseModel):
    event_type: str
    page_url: str
    user_id: str
    session_id: str
    element_id: Optional[str] = None
    element_text: Optional[str] = None
    product_id: Optional[str] = None
    data: Dict[str, Any] = {}
    timestamp: Optional[str] = None

@app.post("/events")
async def collect_event(event: ClickEvent):
    if not event.timestamp:
        event.timestamp = datetime.utcnow().isoformat() + "Z"

    # Promote fields from data to top-level if missing
    if not event.product_id and "product_id" in event.data:
        event.product_id = str(event.data["product_id"])
    if not event.element_id and "element_id" in event.data:
        event.element_id = str(event.data["element_id"])
    if not event.element_text and "element_text" in event.data:
        event.element_text = str(event.data["element_text"])
    
    event_dict = event.dict()
    
    try:
        logger.info(f"Producing event: {event_dict['event_type']} from {event_dict['session_id']}")
        await producer.send(KAFKA_TOPIC, event_dict)
        return {"status": "ok", "message": "Event collected"}
    except Exception as e:
        logger.error(f"Failed to produce event: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
