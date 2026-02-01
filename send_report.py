import os
import re
import requests
import asyncio
import smtplib
import fitz  # PyMuPDF
from io import BytesIO
from email.mime.text import MIMEText
from datetime import datetime
from zoneinfo import ZoneInfo
from telegram import Bot
from playwright.async_api import async_playwright

# Configuration from environment variables
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHANNEL_ID = '@bcskireport'
PDF_URL = 'https://grooming.lumiplan.pro/beaver-creek-grooming-map.pdf'
OPENSNOW_URL = 'https://opensnow.com/location/beavercreek/snow-summary'

# Email-to-SMS configuration
SMTP_EMAIL = os.environ.get('SMTP_EMAIL')  # Your Gmail address
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD')  # Gmail App Password
SMS_RECIPIENTS = os.environ.get('SMS_RECIPIENTS', '')  # Comma-separated email-to-SMS addresses

def send_sms(message):
    """Send SMS via email-to-SMS gateway."""
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        print("Email-to-SMS not configured, skipping...")
        return

    if not SMS_RECIPIENTS:
        print("No SMS recipients configured, skipping...")
        return

    recipients = [r.strip() for r in SMS_RECIPIENTS.split(',') if r.strip()]
    if not recipients:
        print("No SMS recipients configured, skipping...")
        return

    try:
        print(f"Sending SMS to {len(recipients)} recipient(s) via email-to-SMS...")
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(SMTP_EMAIL, SMTP_PASSWORD)

        for recipient in recipients:
            msg = MIMEText(message)
            msg['From'] = SMTP_EMAIL
            msg['To'] = recipient
            msg['Subject'] = ''
            
            server.sendmail(SMTP_EMAIL, recipient, msg.as_string())
            print(f"SMS sent to {recipient}")

        server.quit()
        print("All SMS messages sent successfully!")
    except Exception as e:
        print(f"Error sending SMS: {e}")

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
            hourly = {'times': [], 'temps': [], 'feels': [], 'winds': [], 'clouds': []}

            # Find time slots like "8p Sat", "9p Sat", etc.
            time_pattern = r'(\d{1,2}[ap])\s+(?:Sun|Mon|Tue|Wed|Thu|Fri|Sat)'
            times = re.findall(time_pattern, page_text)
            if times:
                hourly['times'] = times[:6]
                print(f"Found times: {hourly['times']}")

            # Find Temperature row
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
    """Format hourly forecast as mobile-friendly vertical list."""
    if not hourly:
        return None

    times = hourly.get('times', [])
    temps = hourly.get('temps', [])
    feels = hourly.get('feels', [])
    winds = hourly.get('winds', [])

    if not times or not temps:
        return None

    num_hours = min(6, len(times), len(temps))
    if num_hours == 0:
        return None

    lines = []
    for i in range(num_hours):
        time = times[i] if i < len(times) else "?"
        temp = temps[i] if i < len(temps) else "?"
        feel = feels[i] if i < len(feels) else "?"
        wind = winds[i] if i < len(winds) else "?"
        lines.append(f"{time}: {temp}° (feels {feel}°), {wind}")

    return '\n'.join(lines)

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
    page = pdf_document[0]

    matrix = fitz.Matrix(2, 2)
    pix = page.get_pixmap(matrix=matrix)
    image_bytes = pix.tobytes("png")
    pdf_document.close()

    # Build caption
    caption = f'🎿 Beaver Creek Grooming Report - {date_str}'

    # Add snow summary
    snow_parts = []
    if data.get('last_24h'):
        snow_parts.append(f'Last 24hrs: {data["last_24h"]}"')
    if data.get('next_5_days'):
        snow_parts.append(f'Next 5 days: {data["next_5_days"]}"')

    if snow_parts:
        caption += f'\n❄️ Snow: {" | ".join(snow_parts)}'

    # Add hourly forecast
    hourly_text = format_hourly_forecast(data.get('hourly'))
    if hourly_text:
        caption += f'\n\nHourly Forecast:\n{hourly_text}'

    # Send the grooming report to Telegram
    print(f"Sending grooming report to {CHANNEL_ID}...")
    print(f"Caption:\n{caption}")

    await bot.send_photo(
        chat_id=CHANNEL_ID,
        photo=BytesIO(image_bytes),
        caption=caption
    )
    print("Telegram report sent successfully!")

    # Build SMS message (shorter version)
    sms_message = f"Beaver Creek {date_str}\n"
    if snow_parts:
        sms_message += f"Snow: {' | '.join(snow_parts)}\n"

    # Add condensed hourly (first 3 hours)
    hourly = data.get('hourly', {})
    times = hourly.get('times', [])[:3]
    temps = hourly.get('temps', [])[:3]
    feels = hourly.get('feels', [])[:3]

    if times and temps:
        sms_message += "Forecast:\n"
        for i in range(min(3, len(times))):
            temp = temps[i] if i < len(temps) else "?"
            feel = feels[i] if i < len(feels) else "?"
            sms_message += f"{times[i]}: {temp}°F (feels {feel}°)\n"

    sms_message += "grooming.lumiplan.pro/beaver-creek-grooming-map.pdf"

    # Send SMS
    send_sms(sms_message)

if __name__ == '__main__':
    asyncio.run(send_grooming_report())
