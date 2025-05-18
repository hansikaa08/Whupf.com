from fastapi import FastAPI, Depends, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.celery_worker import send_notification_task
from app.database import SessionLocal
from app.models import Notification

app=FastAPI()

def get_db():
    db=SessionLocal()
    try:
        yield db
    finally:
        db.close()

class NotificationRequest(BaseModel):
    user_id: int
    message: str
    notification_type: str

class ConnectionManager:
    def __init__(self):
        self.active_connections=[]
    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        self.active_connections.append({"ws": websocket, "user_id": user_id})
    async def send_personal_message(self, message:str, user_id:int):
        for connection in self.active_connections:
            if connection["user_id"]==user_id:
                await connection["ws"].send_text(message)

manager=ConnectionManager()

@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: int):
    await manager.connect(websocket, user_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.active_connections.remove({"ws":websocket, "user_id": user_id})



@app.post("/notifications")
async def create_notification(request:NotificationRequest, db: Session=Depends(get_db)):
    db_notification=Notification(
        user_id=request.user_id,
        message=request.message,
        notification_type=request.notification_type
    )
    db.add(db_notification)
    db.commit()
    db.refresh(db_notification)

    # pushed to redis using delay
    send_notification_task.delay(db_notification.id)

    return {"message": "queued", "notification_id": db_notification.id}

@app.get("/users/{user_id}/notifications")
def get_notifications(user_id: int, db:Session=Depends(get_db)):
    notifications=db.query(Notification).filter(Notification.user_id==user_id).all()
    return notifications
    