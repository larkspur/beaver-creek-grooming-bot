import os
import requests
import asyncio
import fitz  # PyMuPDF
from io import BytesIO
from telegram import Bot

# Configuration from environment variables
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHANNEL_ID = '@bcskireport'
PDF_URL = 'https://grooming.lumiplan.pro/beaver-creek-grooming-map.pdf'

async def send_grooming_report():
    """Download the Beaver Creek grooming PDF, convert to image, and send to Telegram."""
    bot = Bot(token=BOT_TOKEN)

    # Download the PDF
    print(f"Downloading PDF from {PDF_URL}...")
    response = requests.get(PDF_URL)
    response.raise_for_status()

    # Convert PDF to image
    print("Converting PDF to image...")
    pdf_document = fitz.open(stream=response.content, filetype="pdf")
    page = pdf_document[0]  # Get first page
    
    # Render at 2x resolution for better quality
    matrix = fitz.Matrix(2, 2)
    pix = page.get_pixmap(matrix=matrix)
    image_bytes = pix.tobytes("png")
    pdf_document.close()

    # Send the image to the channel
    print(f"Sending image to {CHANNEL_ID}...")
    await bot.send_photo(
        chat_id=CHANNEL_ID,
        photo=BytesIO(image_bytes),
        caption='🎿 Beaver Creek Grooming Report'
    )
    print("Report sent successfully!")

if __name__ == '__main__':
    asyncio.run(send_grooming_report())
