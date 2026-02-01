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
            await page.wait_for_timeout(2000)
            
            data = {}
            
            # Get snow summary data
            try:
                last_24h = await page.locator('text=Last 24 Hours').locator('..').locator('..').inner_text()
                match = re.search(r'(\d+)"', last_24h)
                if match:
                    data['last_24h'] = match.group(1)
            except:
                pass
            
            try:
                next_5 = await page.locator('text=Next 1-5 Days').locator('..').inner_text()
                match = re.search(r'(\d+)"', next_5)
                if match:
                    data['next_5_days'] = match.group(1)
            except:
                pass
            
            # Get hourly forecast table
            # Find all table rows in the hourly forecast section
            hourly = {'times': [], 'temps': [], 'feels': [], 'winds': [], 'clouds': []}
            
            try:
                # Get time headers from table header row
                table = page.locator('table').first
                
                # Get header row with times
                header_cells = await table.locator('th').all()
                for cell in header_cells[1:7]:  # Skip first column, get next 6
                    text = await cell.inner_text()
                    time_match = re.search(r'(\d+[ap])', text.lower())
                    if time_match:
                        hourly['times'].append(time_match.group(1))
                
                # Get all rows
                rows = await table.locator('tr').all()
                
                for row in rows:
                    row_text = await row.inner_text()
                    cells = await row.locator('td').all()
                    
                    if 'Temperature' in row_text and '°F' in row_text:
                        for cell in cells[:6]:
                            text = await cell.inner_text()
                            num = re.search(r'(\d+)', text)
                            if num:
                                hourly['temps'].append(num.group(1))
                    
                    elif 'Feels Like' in row_text:
                        for cell in cells[:6]:
                            text = await cell.inner_text()
                            num = re.search(r'(-?\d+)', text)
                            if num:
                                hourly['feels'].append(num.group(1))
                    
                    elif 'Wind Speed' in row_text:
                        for cell in cells[:6]:
                            text = await cell.inner_text()
                            wind = re.search(r'([NSEW]+\d+)', text)
                            if wind:
                                hourly['winds'].append(wind.group(1))
                    
                    elif 'Cloud Cover' in row_text:
                        for cell in cells[:6]:
                            text = await cell.inner_text()
                            num = re.search(r'(\d+)', text)
                            if num:
                                hourly['clouds'].append(num.group(1))
                
                data['hourly'] = hourly
                
            except Exception as e:
                print(f"Error parsing hourly table: {e}")
            
            await browser.close()
            print(f"Data fetched: {data}")
            return data
        
    except Exception as e:
        print(f"Error fetching data: {e}")
        return {}

def format_hourly_forecast(hourly):
    """Format hourly forecast as readable text."""
    if not hourly:
        return None
    
    lines = []
    num_hours = min(6, len(hourly.get('temps', [])))
    
    if num_hours == 0:
        return None
    
    # Build each hour as a column
    times = hourly.get('times', [])[:num_hours]
    temps = hourly.get('temps', [])[:num_hours]
    feels = hourly.get('feels', [])[:num_hours]
    winds = hourly.get('winds', [])[:num_hours]
    clouds = hourly.get('clouds', [])[:num_hours]
    
    # Format as simple rows with labels
    if times:
        lines.append("Time:  " + "  ".join(f"{t:>5}" for t in times))
    if temps:
        lines.append("Temp:  " + "  ".join(f"{t:>4}°" for t in temps))
    if feels:
        lines.append("Feels: " + "  ".join(f"{f:>4}°" for f in feels))
    if winds:
        lines.append("Wind:  " + "  ".join(f"{w:>5}" for w in winds))
    if clouds:
        lines.append("Cloud: " + "  ".join(f"{c:>4}%" for c in clouds))
    
    return "\n".join(lines) if lines else None

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
