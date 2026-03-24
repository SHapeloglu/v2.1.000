import os
from dotenv import load_dotenv
load_dotenv('.env')

import database
sender = database.get_sender(5)  # ID'yi değiştirin

print("KEY:", repr(sender.get('AKIARCU2PRVP4GWR46N6')))
print("SECRET:", repr(sender.get('BJD9rqfVx03WrmL4bUDQbLO0Or8NoBsG3brA8MU6PD7e')))
print("REGION:", repr(sender.get('eu-north-1')))


