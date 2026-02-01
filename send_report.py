import os
import requests
import asyncio
from telegram import Bot

# Configuration from environment variables
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHANNEL_ID = '@bcskireport'
PDF_URL = 'https://grooming.lumiplan.pro/beaver-creek-grooming-map.pdf'

async def send_grooming_report():
      """Download the Beaver Creek grooming PDF and send it to the Telegram channel."""
      bot = Bot(token=BOT_TOKEN)

    # Download the PDF
      print(f"Downloading PDF from {PDF_URL}...")
      response = requests.get(PDF_URL)
      response.raise_for_status()

    # Send the PDF to the channel
      print(f"Sending PDF to {CHANNEL_ID}...")
      await bot.send_document(
          chat_id=CHANNEL_ID,
          document=response.content,
          filename='beaver-creek-grooming-report.pdf',
          caption='🎿 Beaver Creek Grooming Report'
      )
      print("Report sent successfully!")

if __name__ == '__main__':
      asyncio.run(send_grooming_report())
