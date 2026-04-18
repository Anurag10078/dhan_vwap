
from urllib.parse import quote
import config
import httpx
from datetime import datetime
import time




# https://api.telegram.org/bot<yor_token>/getUpdates

def telegram_bot_sendtext(bot_message, retries=3):

    encoded_message = quote(str(bot_message))#  + str(datetime.now()))
    send_text = (
        f"https://api.telegram.org/bot{config.BOT_TOKEN}/sendMessage"
        f"?chat_id={config.BOT_CHAT_ID}&parse_mode=HTML&text={encoded_message}"
    )

    attempt = 0
    while attempt <= retries:
        res = None
        try:
            res = httpx.get(send_text, timeout=5)
            
            if res.status_code == 200:
                return res

            print(f"Telegram bad status {res.status_code}: {res.text}")

        except Exception as e:
            print(f"Error sending Telegram msg (attempt {attempt+1}): {e}")

        attempt += 1

        if attempt <= retries:
            time.sleep(1 * attempt)  

    return None

if __name__ == "__main__":
    telegram_bot_sendtext("Hello from the other side!") 