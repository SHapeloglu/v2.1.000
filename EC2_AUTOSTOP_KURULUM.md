# EC2 Auto-Stop Kurulum Talimatı

Script gönderimi bitirince EC2'yu otomatik kapatmak için
EC2 instance'ına bir IAM rolü atamanız gerekiyor.

## Adımlar

### 1. IAM Rolü Oluştur
- AWS Console → IAM → Roles → "Create role"
- "AWS service" → "EC2" seç
- Policy olarak şunu ekle (inline veya yeni policy):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "ec2:StopInstances",
      "Resource": "*"
    }
  ]
}
```

- Role adı: `mailsender-ec2-role` (istediğiniz bir isim)

### 2. Rolü EC2'ya Ata
- EC2 Console → Instance seç → Actions → Security → "Modify IAM role"
- Oluşturduğun rolü seç → Save

### 3. Kullanım
- Bulk Send sayfasında "Gönderim bitince EC2'yu otomatik kapat" toggle'ını aç
- Gönderim tamamlanınca EC2 otomatik olarak Stop edilir
- Veriler ve script kaybolmaz (Terminate değil Stop)

## Not
Bu özellik sadece EC2 üzerinde çalışırken aktif olur.
Lokal geliştirme ortamında toggle otomatik gizlenir.
