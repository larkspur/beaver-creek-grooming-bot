import os
import re
import requests
import asyncio
import fitz  # PyMuPDF
from io import BytesIO
from datetime import datetime
from zoneinfo import ZoneInfo
from telegram import Bot
from bs4 import BeautifulSoup

# Configuration from environment variables
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHANNEL_ID = '@bcskireport'
PDF_URL = 'https://grooming.lumiplan.pro/beaver-creek-grooming-map.pdf'
OPENSNOW_URL = 'https://opensnow.com/location/beavercreek/snow-summary'

def get_ordinal_suffix(day):
    """Return the ordinal suffix for a day (1st, 2nd, 3rd, 4th, etc.)"""
    if 11 <= day <= 13:
        return 'th'
    return {1: 'st', 2: 'nd', 3: 'rd'}.get(day % 10, 'th')

def get_formatted_date():
    """Return date formatted like 'Jan 31st' in Mountain Time"""
    mountain_tz = ZoneInfo('America/Denver')
    now = datetime.now(mountain_tz)
    day = now.day
    suffix = get_ordinal_suffix(day)
    return now.strftime(f'%b {day}{suffix}')

def get_snow_data():
    """Fetch snow data from OpenSnow."""
    try:
        print(f"Fetching snow data from {OPENSNOW_URL}...")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        response = requests.get(OPENSNOW_URL, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        text = soup.get_text()
        
        # Parse the snow data from the page text
        # Looking for patterns like "Last 24 Hours 0"" and "Next 1-5 Days 0""
        last_24h = None
        next_5_days = None
        
        # Find "Last 24 Hours" followed by a number
        match_24h = re.search(r'Last 24 Hours\s*(\d+)"', text)
        if match_24h:
            last_24h = match_24h.group(1)
        
        # Find "Next 1-5 Days" followed by a number  
        match_next = re.search(r'Next 1-5 Days\s*(\d+)"', text)
        if match_next:
            next_5_days = match_next.group(1)
            
        print(f"Snow data: Last 24h={last_24h}\", Next 5 days={next_5_days}\"")
        return last_24h, next_5_days
        
    except Exception as e:
        print(f"Error fetching snow data: {e}")
        return None, None

async def send_grooming_report():
    """Download the Beaver Creek grooming PDF, convert to image, and send to Telegram."""
    bot = Bot(token=BOT_TOKEN)
    date_str = get_formatted_date()
    
    # Get snow data
    last_24h, next_5_days = get_snow_data()

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

    # Build caption with snow data
    caption = f'🎿 Beaver Creek Grooming Report - {date_str}'
    
    if last_24h is not None or next_5_days is not None:
        snow_info = []
        if last_24h is not None:
            snow_info.append(f'Last 24hrs: {last_24h}"')
        if next_5_days is not None:
            snow_info.append(f'Next 5 days: {next_5_days}"')
        caption += f'\n❄️ {" | ".join(snow_info)}'

    # Send the grooming report
    print(f"Sending grooming report to {CHANNEL_ID}...")
    await bot.send_photo(
        chat_id=CHANNEL_ID,
        photo=BytesIO(image_bytes),
        caption=caption
    )
    print("Report sent successfully!")

if __name__ == '__main__':
    asyncio.run(send_grooming_report())
