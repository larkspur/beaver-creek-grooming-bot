import os
import re
import requests
import asyncio
import fitz  # PyMuPDF
from io import BytesIO
from datetime import datetime
from zoneinfo import ZoneInfo
from telegram import Bot
from playwright.async_api import async_playwright

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

async def get_opensnow_data():
    """Fetch snow and hourly weather data from OpenSnow using Playwright."""
    try:
        print(f"Fetching data from {OPENSNOW_URL}...")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            
            await page.goto(OPENSNOW_URL, wait_until='networkidle')
            await page.wait_for_timeout(3000)
            
            data = {}
            
            # Get full page text for parsing
            page_text = await page.inner_text('body')
            print(f"Page text length: {len(page_text)}")
            
            # Parse snow data
            match_24h = re.search(r'Last 24 Hours\s*(\d+)"', page_text)
            if match_24h:
                data['last_24h'] = match_24h.group(1)
            
            match_next = re.search(r'Next 1-5 Days\s*(\d+)"', page_text)
            if match_next:
                data['next_5_days'] = match_next.group(1)
            
            # Parse hourly forecast
            # Look for the Hourly Forecast section
            hourly = {'times': [], 'temps': [], 'feels': [], 'winds': [], 'clouds': []}
            
            # Find time slots like "8p Sat", "9p Sat", etc.
            time_pattern = r'(\d{1,2}[ap])\s+(?:Sun|Mon|Tue|Wed|Thu|Fri|Sat)'
            times = re.findall(time_pattern, page_text)
            if times:
                hourly['times'] = times[:6]
                print(f"Found times: {hourly['times']}")
            
            # Find Temperature row - looking for pattern after "Temperature °F"
            temp_section = re.search(r'Temperature\s*°?F\s*([\d\s]+?)(?=Feels Like)', page_text, re.DOTALL)
            if temp_section:
                temps = re.findall(r'\b(\d{1,2})\b', temp_section.group(1))
                hourly['temps'] = temps[:6]
                print(f"Found temps: {hourly['temps']}")
            
            # Find Feels Like row
            feels_section = re.search(r'Feels Like\s*°?F\s*([-\d\s]+?)(?=Rel|Humidity)', page_text, re.DOTALL)
            if feels_section:
                feels = re.findall(r'(-?\d{1,2})\b', feels_section.group(1))
                hourly['feels'] = feels[:6]
                print(f"Found feels: {hourly['feels']}")
            
            # Find Wind Speed row
            wind_section = re.search(r'Wind Speed\s*mph\s*([A-Za-z\d\s]+?)(?=Wind Gust)', page_text, re.DOTALL)
            if wind_section:
                winds = re.findall(r'([NSEW]{1,3}\d{1,2})', wind_section.group(1))
                hourly['winds'] = winds[:6]
                print(f"Found winds: {hourly['winds']}")
            
            # Find Cloud Cover row
            cloud_section = re.search(r'Cloud Cover\s*%?\s*([\d\s]+?)(?=How to read|$)', page_text, re.DOTALL)
            if cloud_section:
                clouds = re.findall(r'\b(\d{1,3})\b', cloud_section.group(1))
                hourly['clouds'] = clouds[:6]
                print(f"Found clouds: {hourly['clouds']}")
            
            data['hourly'] = hourly
            
            await browser.close()
            print(f"Data fetched: {data}")
            return data
        
    except Exception as e:
        print(f"Error fetching data: {e}")
        import traceback
        traceback.print_exc()
        return {}

def format_hourly_forecast(hourly):
    """Format hourly forecast as readable text."""
    if not hourly:
        return None
    
    times = hourly.get('times', [])
    temps = hourly.get('temps', [])
    feels = hourly.get('feels', [])
    winds = hourly.get('winds', [])
    clouds = hourly.get('clouds', [])
    
    # Need at least times and temps
    if not times or not temps:
        return None
    
    num_hours = min(6, len(times), len(temps))
    if num_hours == 0:
        return None
    
    lines = []
    lines.append("Time:  " + "  ".join(f"{times[i]:>5}" for i in range(num_hours)))
    lines.append("Temp:  " + "  ".join(f"{temps[i]:>4}°" for i in range(min(num_hours, len(temps)))))
    
    if feels and len(feels) >= num_hours:
        lines.append("Feels: " + "  ".join(f"{feels[i]:>4}°" for i in range(num_hours)))
    
    if winds and len(winds) >= num_hours:
        lines.append("Wind:  " + "  ".join(f"{winds[i]:>5}" for i in range(num_hours)))
    
    if clouds and len(clouds) >= num_hours:
        lines.append("Cloud: " + "  ".join(f"{clouds[i]:>4}%" for i in range(num_hours)))
    
    return "\n".join(lines)

async def send_grooming_report():
    """Download the Beaver Creek grooming PDF, convert to image, and send to Telegram."""
    bot = Bot(token=BOT_TOKEN)
    date_str = get_formatted_date()
    
    # Get OpenSnow data
    data = await get_opensnow_data()

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
    
    # Add hourly forecast
    hourly_text = format_hourly_forecast(data.get('hourly'))
    if hourly_text:
        caption += f'\n\nHourly Forecast:\n{hourly_text}'

    # Send the grooming report
    print(f"Sending grooming report to {CHANNEL_ID}...")
    print(f"Caption:\n{caption}")
    await bot.send_photo(
        chat_id=CHANNEL_ID,
        photo=BytesIO(image_bytes),
        caption=caption
    )
    print("Report sent successfully!")

if __name__ == '__main__':
    asyncio.run(send_grooming_report())
