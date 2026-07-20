import os
from dotenv import load_dotenv
from core.client import Rob

def main():
    load_dotenv(".env")
    TOKEN = os.getenv("TOKEN", None)

    bot = Rob()
    try:
        bot.run(TOKEN)
    except KeyboardInterrupt:
        print(':: Program interrupted, shutting down gracefully')
        bot.close()
    except Exception as e:
        print(f':: Unknown error: {e}')

if __name__ == "__main__":
    main()