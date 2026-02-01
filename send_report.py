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

def get_snow_and_weather_data():
    """Fetch snow data and hourly forecast from OpenSnow."""
    try:
        print(f"Fetching data from {OPENSNOW_URL}...")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        response = requests.get(OPENSNOW_URL, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        text = soup.get_text()
        
        # Parse snow data
        last_24h = None
        next_5_days = None
        
        match_24h = re.search(r'Last 24 Hours\s*(\d+)"', text)
        if match_24h:
            last_24h = match_24h.group(1)
        
        match_next = re.search(r'Next 1-5 Days\s*(\d+)"', text)
        if match_next:
            next_5_days = match_next.group(1)
        
        # Parse hourly forecast from the table
        # Look for the hourly data pattern
        hourly_data = []
        
        # Find temperature row - look for pattern like "Temperature °F" followed by numbers
        temp_match = re.search(r'Temperature\s*°?F?\s*([\d\s]+?)(?=Feels Like)', text, re.DOTALL)
        feels_match = re.search(r'Feels Like\s*°?F?\s*([\d\s-]+?)(?=Rel|Humidity)', text, re.DOTALL)
        wind_match = re.search(r'Wind Speed\s*mph\s*([NSEW\d\s]+?)(?=Wind Gust)', text, re.DOTALL)
        cloud_match = re.search(r'Cloud Cover\s*%?\s*([\d\s]+?)(?=How|$)', text, re.DOTALL)
        
        temps = []
        feels = []
        winds = []
        clouds = []
        
        if temp_match:
            temps = re.findall(r'\d+', temp_match.group(1))[:6]
        if feels_match:
            feels = re.findall(r'-?\d+', feels_match.group(1))[:6]
        if wind_match:
            winds = re.findall(r'[NSEW]+\d+', wind_match.group(1))[:6]
        if cloud_match:
            clouds = re.findall(r'\d+', cloud_match.group(1))[:6]
        
        # Get time headers
        time_match = re.search(r'(\d+[ap])\s+\w+\s+(\d+[ap])\s+\w+\s+(\d+[ap])\s+\w+\s+(\d+[ap])\s+\w+\s+(\d+[ap])\s+\w+\s+(\d+[ap])', text)
        times = []
        if time_match:
            times = list(time_match.groups())[:6]
        
        hourly = {
            'times': times,
            'temps': temps,
            'feels': feels,
            'winds': winds,
            'clouds': clouds
        }
        
        print(f"Snow: 24h={last_24h}\", Next 5 days={next_5_days}\"")
        print(f"Hourly temps: {temps}")
        
        return last_24h, next_5_days, hourly
        
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None, None, None

def format_hourly_forecast(hourly):
    """Format hourly forecast as text."""
    if not hourly or not hourly.get('temps'):
        return None
    
    lines = []
    
    # Time header
    if hourly['times']:
        lines.append("⏰ " + "  ".join(f"{t:>4}" for t in hourly['times'][:6]))
    
    # Temperature
    if hourly['temps']:
        lines.append("🌡️ " + "  ".join(f"{t:>3}°" for t in hourly['temps'][:6]))
    
    # Feels like
    if hourly['feels']:
        lines.append("🥶 " + "  ".join(f"{f:>3}°" for f in hourly['feels'][:6]))
    
    # Wind
    if hourly['winds']:
        lines.append("💨 " + "  ".join(f"{w:>4}" for w in hourly['winds'][:6]))
    
    # Cloud cover
    if hourly['clouds']:
        lines.append("☁️ " + "  ".join(f"{c:>3}%" for c in hourly['clouds'][:6]))
    
    return "\n".join(lines) if lines else None

async def send_grooming_report():
    """Download the Beaver Creek grooming PDF, convert to image, and send to Telegram."""
    bot = Bot(token=BOT_TOKEN)
    date_str = get_formatted_date()
    
    # Get snow and weather data
    last_24h, next_5_days, hourly = get_snow_and_weather_data()

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
    
    # Add snow summary
    if last_24h is not None or next_5_days is not None:
        snow_info = []
        if last_24h is not None:
            snow_info.append(f'Last 24hrs: {last_24h}"')
        if next_5_days is not None:
            snow_info.append(f'Next 5 days: {next_5_days}"')
        caption += f'\n❄️ {" | ".join(snow_info)}'
    
    # Add hourly forecast
    hourly_text = format_hourly_forecast(hourly)
    if hourly_text:
        caption += f'\n\n{hourly_text}'

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
