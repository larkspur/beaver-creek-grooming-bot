import os
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

async def capture_snow_summary():
    """Capture a screenshot of the OpenSnow snow summary chart."""
    try:
        print(f"Capturing snow summary from {OPENSNOW_URL}...")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page(viewport={'width': 1200, 'height': 800})
            
            await page.goto(OPENSNOW_URL, wait_until='networkidle')
            
            # Wait for the page to fully load
            await page.wait_for_timeout(3000)
            
            # Dismiss any cookie banner if present
            try:
                cookie_btn = page.locator('text=Accept Cookies')
                if await cookie_btn.count() > 0:
                    await cookie_btn.click()
                    await page.wait_for_timeout(500)
            except:
                pass
            
            # Scroll to top to ensure we capture the right area
            await page.evaluate("window.scrollTo(0, 0)")
            await page.wait_for_timeout(500)
            
            # Capture just the Snow Summary section at the top
            # The section starts around y=100 (after header) and is about 180px tall
            screenshot_bytes = await page.screenshot(
                clip={'x': 50, 'y': 100, 'width': 1100, 'height': 180}
            )
            
            await browser.close()
            print("Snow summary captured successfully!")
            return screenshot_bytes
            
    except Exception as e:
        print(f"Error capturing snow summary: {e}")
        return None

async def send_grooming_report():
    """Download the Beaver Creek grooming PDF, convert to image, and send to Telegram."""
    bot = Bot(token=BOT_TOKEN)
    date_str = get_formatted_date()
    
    # Capture snow summary screenshot
    snow_screenshot = await capture_snow_summary()

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

    # Send snow summary first if available
    if snow_screenshot:
        print(f"Sending snow summary to {CHANNEL_ID}...")
        await bot.send_photo(
            chat_id=CHANNEL_ID,
            photo=BytesIO(snow_screenshot),
            caption=f'❄️ Snow Summary - {date_str}'
        )

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
