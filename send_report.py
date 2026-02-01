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
SNOW_REPORT_URL = 'https://www.onthesnow.com/colorado/beaver-creek/skireport'

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
    """Fetch 24hr and 48hr snowfall totals from OnTheSnow."""
    try:
        print(f"Fetching snow data from {SNOW_REPORT_URL}...")
        headers = {'User-Agent': 'Mozilla/5.0 (compatible; GroomingBot/1.0)'}
        response = requests.get(SNOW_REPORT_URL, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find the Recent Snowfall table
        # Look for the snowfall data in the page
        text = soup.get_text()
        
        # Try to find 24h snowfall - it's typically in a table
        # The format on the page shows: Sun | Mon | Tue | Wed | Thu | 24h
        snow_24h = None
        snow_48h = None
        
        # Look for patterns like "24h" followed by a number with inches
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            for i, row in enumerate(rows):
                cells = row.find_all(['td', 'th'])
                cell_texts = [cell.get_text(strip=True) for cell in cells]
                
                # Check if this is the header row with "24h"
                if '24h' in cell_texts:
                    # The next row should have the values
                    if i + 1 < len(rows):
                        value_row = rows[i + 1]
                        value_cells = value_row.find_all(['td', 'th'])
                        values = [cell.get_text(strip=True) for cell in value_cells]
                        
                        # Get 24h value (last column) and previous day for 48h calculation
                        if len(values) >= 2:
                            # 24h is typically the last value
                            snow_24h_str = values[-1].replace('"', '').replace("'", '')
                            prev_day_str = values[-2].replace('"', '').replace("'", '')
                            
                            try:
                                snow_24h = float(snow_24h_str) if snow_24h_str else 0
                                prev_day = float(prev_day_str) if prev_day_str else 0
                                snow_48h = snow_24h + prev_day
                            except ValueError:
                                pass
                    break
        
        if snow_24h is not None:
            print(f"Snow data: 24h={snow_24h}\", 48h={snow_48h}\"")
            return snow_24h, snow_48h
        
        print("Could not parse snow data from page")
        return None, None
        
    except Exception as e:
        print(f"Error fetching snow data: {e}")
        return None, None

async def send_grooming_report():
    """Download the Beaver Creek grooming PDF, convert to image, and send to Telegram."""
    bot = Bot(token=BOT_TOKEN)
    date_str = get_formatted_date()
    
    # Get snow data
    snow_24h, snow_48h = get_snow_data()

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

    # Build caption
    caption = f'🎿 Beaver Creek Grooming Report - {date_str}'
    if snow_24h is not None:
        caption += f'\n❄️ 24hr: {snow_24h}" | 48hr: {snow_48h}"'

    # Send the image to the channel
    print(f"Sending image to {CHANNEL_ID}...")
    await bot.send_photo(
        chat_id=CHANNEL_ID,
        photo=BytesIO(image_bytes),
        caption=caption
    )
    print("Report sent successfully!")

if __name__ == '__main__':
    asyncio.run(send_grooming_report())
