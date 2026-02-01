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

def get_opensnow_data():
    """Fetch snow and current weather data from OpenSnow."""
    try:
        print(f"Fetching data from {OPENSNOW_URL}...")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        response = requests.get(OPENSNOW_URL, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        text = soup.get_text()
        
        data = {}
        
        # Parse snow data
        match_24h = re.search(r'Last 24 Hours\s*(\d+)"', text)
        if match_24h:
            data['last_24h'] = match_24h.group(1)
        
        match_next = re.search(r'Next 1-5 Days\s*(\d+)"', text)
        if match_next:
            data['next_5_days'] = match_next.group(1)
        
        # Parse current conditions from "Right Now" section
        # Looking for patterns like "19 °F" and "feels like 10 °F"
        temp_match = re.search(r'Right Now.*?(\d+)\s*°F', text, re.DOTALL)
        if temp_match:
            data['temp'] = temp_match.group(1)
        
        feels_match = re.search(r'feels like\s*(\d+)\s*°F', text, re.IGNORECASE)
        if feels_match:
            data['feels_like'] = feels_match.group(1)
        
        wind_match = re.search(r'(\d+)\s*mph.*?([NSEW]+)\s*gusts', text, re.IGNORECASE)
        if wind_match:
            data['wind_speed'] = wind_match.group(1)
            data['wind_dir'] = wind_match.group(2)
        
        gust_match = re.search(r'gusts to\s*(\d+)', text, re.IGNORECASE)
        if gust_match:
            data['wind_gust'] = gust_match.group(1)
        
        # Get weather description (Clear, Cloudy, etc.)
        weather_match = re.search(r'(Clear|Cloudy|Snow|Rain|Partly Cloudy|Overcast)', text, re.IGNORECASE)
        if weather_match:
            data['weather'] = weather_match.group(1).title()
        
        print(f"Data fetched: {data}")
        return data
        
    except Exception as e:
        print(f"Error fetching data: {e}")
        return {}

async def send_grooming_report():
    """Download the Beaver Creek grooming PDF, convert to image, and send to Telegram."""
    bot = Bot(token=BOT_TOKEN)
    date_str = get_formatted_date()
    
    # Get OpenSnow data
    data = get_opensnow_data()

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
    caption = f'Beaver Creek Grooming Report - {date_str}'
    
    # Add snow summary
    snow_parts = []
    if data.get('last_24h'):
        snow_parts.append(f'Last 24hrs: {data["last_24h"]}"')
    if data.get('next_5_days'):
        snow_parts.append(f'Next 5 days: {data["next_5_days"]}"')
    if snow_parts:
        caption += f'\nSnow: {" | ".join(snow_parts)}'
    
    # Add current conditions
    conditions = []
    if data.get('temp'):
        temp_str = f'{data["temp"]}°F'
        if data.get('feels_like'):
            temp_str += f' (feels {data["feels_like"]}°F)'
        conditions.append(f'Temp: {temp_str}')
    
    if data.get('weather'):
        conditions.append(f'Sky: {data["weather"]}')
    
    if data.get('wind_speed'):
        wind_str = f'{data.get("wind_dir", "")}{data["wind_speed"]}mph'
        if data.get('wind_gust'):
            wind_str += f', gusts {data["wind_gust"]}mph'
        conditions.append(f'Wind: {wind_str}')
    
    if conditions:
        caption += '\n' + '\n'.join(conditions)

    # Send the grooming report
    print(f"Sending grooming report to {CHANNEL_ID}...")
    print(f"Caption: {caption}")
    await bot.send_photo(
        chat_id=CHANNEL_ID,
        photo=BytesIO(image_bytes),
        caption=caption
    )
    print("Report sent successfully!")

if __name__ == '__main__':
    asyncio.run(send_grooming_report())
