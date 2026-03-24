import os
from dotenv import load_dotenv
load_dotenv('.env')

from database import _fernet, decrypt_password

enc = "gAAAAABprNiah32NBbcCjJliHKdZnqtkDJ7JaD7Zy5_oloXzw7yuvDHwf31waXIhjQ_yRc-5z__rpEJbZdVW-w9KUYE96-rx7q0SfLXZ9sMwZUMFDQ0iMLE="

result = decrypt_password(enc)
print("Çözülen değer:", repr(result))
print("SECRET_KEY:", os.getenv('SECRET_KEY'))