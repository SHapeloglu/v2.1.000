"""
sns_handler.py — AWS SNS bildirimlerini işler
"""
from flask import Blueprint, request, jsonify
import json
from database import add_to_suppression, log_send

sns_bp = Blueprint('sns', __name__, url_prefix='/sns')

@sns_bp.route('/ses-notification', methods=['POST'])
def handle_ses_notification():
    """SES'ten gelen SNS bildirimlerini işler"""
    try:
        # SNS bildirimini al
        notification = json.loads(request.data)
        
        # Subscription doğrulama isteği mi?
        if notification.get('Type') == 'SubscriptionConfirmation':
            # Subscribe URL'ine istek yap
            import requests
            requests.get(notification['SubscribeURL'])
            return jsonify({'success': True, 'message': 'Subscribed'})
        
        # Bildirim tipi
        if notification.get('Type') == 'Notification':
            message = json.loads(notification['Message'])
            
            # Bildirim tipine göre işlem
            notification_type = message.get('notificationType')
            
            if notification_type == 'Bounce':
                bounce = message.get('bounce', {})
                bounce_type = bounce.get('bounceType')
                
                for recipient in bounce.get('bouncedRecipients', []):
                    email = recipient.get('emailAddress')
                    reason = 'bounce'
                    
                    # Hard bounce ise bastırma listesine ekle
                    if bounce_type == 'Permanent':
                        add_to_suppression(email, reason, 'sns-bounce')
                        print(f"Hard bounce eklendi: {email}")
                    
                    # Log'a kaydet
                    log_send(None, None, email, 'BOUNCE', 'failed', f'Bounce: {bounce_type}')
                    
            elif notification_type == 'Complaint':
                complaint = message.get('complaint', {})
                
                for recipient in complaint.get('complainedRecipients', []):
                    email = recipient.get('emailAddress')
                    # Complaint alınanları bastırma listesine ekle
                    add_to_suppression(email, 'complaint', 'sns-complaint')
                    log_send(None, None, email, 'COMPLAINT', 'failed', 'Spam complaint')
                    
            elif notification_type == 'Delivery':
                # Teslimat başarılı, log'a kaydet
                delivery = message.get('delivery', {})
                for recipient in delivery.get('recipients', []):
                    print(f"Teslimat başarılı: {recipient}")
        
        return jsonify({'success': True})
        
    except Exception as e:
        print(f"SNS handler hatası: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# SNS yapılandırma fonksiyonu
def setup_sns_notifications():
    """SES için SNS topic yapılandırmasını yapar"""
    import boto3
    from database import get_sender
    
    # İlk aktif SES göndericiyi bul
    senders = get_senders(active_only=True)
    ses_sender = next((s for s in senders if s['sender_mode'] == 'ses'), None)
    
    if not ses_sender:
        print("SES gönderici bulunamadı")
        return None
    
    # AWS credentials
    aws_key = ses_sender.get('aws_access_key', '')
    aws_secret = ses_sender.get('aws_secret_key', '')
    aws_region = ses_sender.get('aws_region', 'us-east-1')
    
    # SNS client oluştur
    session = boto3.Session(
        aws_access_key_id=aws_key,
        aws_secret_access_key=aws_secret,
        region_name=aws_region
    )
    
    sns_client = session.client('sns')
    
    # Topic oluştur
    response = sns_client.create_topic(Name='ses-notifications')
    topic_arn = response['TopicArn']
    
    # Subscription oluştur (ngrok veya public URL gerekli)
    # Bu kısmı manuel yapmak daha kolay
    print(f"Topic ARN: {topic_arn}")
    print("AWS Console'dan bu topice subscription ekleyin")
    
    return topic_arn