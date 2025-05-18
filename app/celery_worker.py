from celery import Celery
from app.models import Notification
from app.database import SessionLocal
import os
from dotenv import load_dotenv
from sendgrid.helpers.mail import Mail
from sendgrid import SendGridAPIClient
from twilio.rest import Client
from celery.exceptions import MaxRetriesExceededError
from sqlalchemy.orm import Session
import logging
import requests
try:
    requests.get("https://api.sendgrid.com", timeout=5)
    print("Network OK")
except Exception as e:
    print(f"Network error: {e}")

load_dotenv()  # Loads .env file


# Queues using Redis
app=Celery('tasks', broker='redis://localhost:6379/0')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app.conf.task_default_retry_delay = 30
app.conf.task_max_retries = 3


def send_email(to_email:str, subject:str, content:str):
    message=Mail(
        from_email="saininihalhansika@gmail.com",
        to_emails=to_email,
        subject=subject,
        html_content=content
    )
    try:
        sg=SendGridAPIClient(os.getenv("SENDGRID_API_KEY"))
        response=sg.send(message)
        if response.status_code == 202:
            logger.info(f"Email sent to {to_email}")
            return True
        logger.error(f"Email failed with status {response.status_code}")
        return False
    except Exception as e:
        logger.error(f"Email error: {str(e)}")
        return False
    

def send_sms(to_phone: str, message:str):
    try:
        client=Client(
            os.getenv("TWILIO_ACCOUNT_SID"),
            os.getenv("TWILIO_AUTH_TOKEN")
        )
        response=client.message.create(
            body=message,
            from_=os.getenv("TWILIO_PHONE_NUMBER"),
            to=to_phone
        )
        if response.sid:
            logger.info(f"SMS sent to {to_phone}")
            return True
        logger.error("SMS failed - no SID returned")
        return False
    except Exception as e:
        print(f"SMS error: {e}")
        return False


@app.task(bind=True, max_retries=3)
def send_notification_task(self, notification_id: int):
    db=SessionLocal()
    notification = None

    try:
        notification=db.query(Notification).filter(Notification.id==notification_id).first()
        if not notification:
            raise ValueError(f"Notification ID {notification_id} not found")
        # print(f"Sending{notification.notification_type} notification:{notification.message}")

        if notification.notification_type == "email":
            success = send_email(
                to_email=f"nihalhansika08@gmail.com", 
                subject="New Notification",
                content=notification.message
            )
        elif notification.notification_type == "sms":
            success = send_sms(
                to_phone="+91-9410511763", 
                message=notification.message
            )
        else:  
            success = True 
            logger.info(f"In-app notification: {notification.message}")
            

        notification.status = "sent" if success else "failed"        
        db.commit()

        if not success:
            raise ValueError(f"Failed to send {notification.notification_type} notification")

    except Exception as e:
        db.rollback()
        if notification:
            notification.status = "failed"
            db.commit()
        
        try:
            logger.warning(f"Attempt {self.request.retries + 1}/{self.max_retries} failed. Retrying...")
            raise self.retry(exc=e, countdown=30 * (self.request.retries + 1))  
        except MaxRetriesExceededError:
            logger.error(f"Permanently failed after {self.max_retries} retries: {str(e)}")
            
    finally:
        db.close()




    