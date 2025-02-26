import os
import requests
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from datetime import datetime, timedelta
from transformers import pipeline
import tensorflow as tf
import warnings
from hashlib import md5
import time

# Suppress unnecessary warnings
warnings.filterwarnings("ignore")
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
tf.get_logger().setLevel('ERROR')

# Configuration for API keys
API_KEYS = {
    "newsapi": "18272c0386d242968a28372381bffd07"  # Ensure this is your valid NewsAPI key
}

# Email configuration
EMAIL_CONFIG = {
    "sender_email": "your-email@gmail.com",  # Update with your email
    "sender_password": "your-app-password",  # Update with your app password (not your regular password)
    "recipients": ["venkatakrishnan2222@gmail.com", "vr4653@srmist.edu.in"],
    "subject": "AI News Report - " + datetime.now().strftime('%Y-%m-%d')
}

# AI-related keywords to filter relevant articles
AI_KEYWORDS = ["AI", "Artificial Intelligence", "Machine Learning", "ML", "Deep Learning", "NLP", "Generative AI"]

# Preferred sources (trusted mainstream news sites)
TRUSTED_SOURCES = "bbc-news,cnn,the-verge,wired,techcrunch"

# Function to generate a unique hash for each article
def get_hash(content):
    return md5(content.encode('utf-8')).hexdigest()

# Cache to prevent processing the same article multiple times
cache = set()

# Function to fetch news from the API (restricting to trusted sources)
def fetch_news(start_date, end_date, query="Artificial Intelligence", num_articles=10):
    url = f"https://newsapi.org/v2/everything?q={query}&from={start_date}&to={end_date}&sources={TRUSTED_SOURCES}&sortBy=publishedAt&apiKey={API_KEYS['newsapi']}&pageSize={num_articles}&language=en"
    
    print(f"Fetching news from URL: {url}")  # Debugging print
    response = requests.get(url)
    
    if response.status_code == 200:
        articles = response.json().get("articles", [])
        print(f"Total articles fetched: {len(articles)}")  # Debugging print
        return articles
    else:
        print(f"Failed to fetch news: HTTP {response.status_code} - {response.text}")
        return []

# Function to clean up content and remove "[+ chars]"
def clean_content(text):
    if text:
        text = text.split("[+")[0].strip()  # Remove everything after "[+"
        return text
    return ""

# Function to summarize text using the Hugging Face Transformers pipeline
def summarize_text(text):
    try:
        summarizer = pipeline("summarization", model="t5-small")
        
        # Increase summary size even more (4x bigger)
        max_len = min(len(text) // 2, 720)  # More detailed summary
        min_len = max_len // 2

        summary = summarizer(text, max_length=max_len, min_length=min_len, do_sample=False)
        return summary[0]["summary_text"]
    except Exception as e:
        print(f"Error during summarization: {e}")
        return None

# Function to filter relevant AI news and remove duplicates
def filter_ai_articles(articles):
    filtered_articles = []

    for article in articles:
        title = article["title"]
        description = article.get("description", "")
        content = clean_content(article.get("content", ""))  # Clean content to remove "[+ chars]"
        url = article["url"]

        # If "content" is too short, use "description"
        if len(content) < 100:
            content = clean_content(description)

        # Create a hash to check for duplicates
        content_hash = get_hash(title + content)

        # Check if the article is primarily about AI
        is_ai_article = sum(
            keyword.lower() in (title + description + content).lower()
            for keyword in AI_KEYWORDS
        ) >= 2  # Require at least 2 AI-related keywords

        # Check if the article is unique and primarily about AI
        if content_hash not in cache and is_ai_article:
            cache.add(content_hash)
            filtered_articles.append(article)

    return filtered_articles

# Function to create and save a report of the articles as a text file
from fpdf import FPDF

def save_articles_as_pdf(articles):
    filtered_articles = filter_ai_articles(articles)
    pdf_filename = "news_report_new.pdf"
    
    pdf = FPDF()
    pdf.add_page()
    # Make sure to handle the font path correctly for deployment
    # For Render, you'll need to use a relative path or install the font 
    try:
        # Try to use a standard font first
        pdf.set_font('Arial', size=12)
    except Exception:
        try:
            # If Arial fails, try DejaVu with absolute path
            pdf.add_font('DejaVu', '', r'DejaVuSans.ttf', uni=True)
            pdf.set_font('DejaVu', size=12)
        except Exception as e:
            # If all fails, use built-in Helvetica
            print(f"Font error: {e}, using default font")
            pdf.set_font('Helvetica', size=12)

    # Add title to the PDF
    pdf.set_font_size(16)
    pdf.cell(200, 10, "AI News Report", ln=True, align='C')
    pdf.set_font_size(12)
    pdf.cell(200, 10, f"Generated on {datetime.now().strftime('%Y-%m-%d')}", ln=True, align='C')
    pdf.ln(10)
    
    if not filtered_articles:
        pdf.cell(200, 10, "No relevant AI news found.")
    else:
        # Use link functionality for clickable URLs
        for i, article in enumerate(filtered_articles):
            title = article["title"]
            url = article["url"]
            content = clean_content(article.get("content", ""))

            if len(content) < 100:
                content = clean_content(article.get("description", ""))

            # Set a blue color for title to indicate it's a link
            pdf.set_text_color(0, 0, 255)
            pdf.cell(200, 10, f"{i+1}. {title}", ln=True)
            
            # Add clickable link
            pdf.set_text_color(0, 0, 255)
            # The link text
            pdf.cell(30, 10, "Read More:", ln=0)
            
            # The actual link that's clickable
            pdf.set_font('', 'U')  # Underline to indicate link
            link_text = url if len(url) < 80 else url[:77] + "..."
            pdf.cell(170, 10, link_text, ln=1, link=url)
            pdf.set_font('', '')  # Remove underline
            
            # Reset text color for summary
            pdf.set_text_color(0, 0, 0)
            
            if content:
                summary = summarize_text(content)
                if summary:
                    pdf.multi_cell(0, 10, f"Summary: {summary}")
                else:
                    pdf.multi_cell(0, 10, "Summary: Could not summarize")
            else:
                pdf.multi_cell(0, 10, "Summary: No content available")
            
            pdf.ln(5)  # Add space between articles

    pdf.output(pdf_filename)
    print(f"PDF report saved as {pdf_filename}")
    return pdf_filename, filtered_articles

# Function to send email with the PDF attachment
def send_email(pdf_filename, articles):
    # Check if PDF exists and wait for it to be fully written
    max_wait = 60  # Maximum wait time in seconds
    wait_interval = 5  # Check every 5 seconds
    total_waited = 0
    
    while not os.path.exists(pdf_filename) and total_waited < max_wait:
        print(f"Waiting for PDF to be generated... ({total_waited}s)")
        time.sleep(wait_interval)
        total_waited += wait_interval
    
    if not os.path.exists(pdf_filename):
        print(f"Error: PDF file {pdf_filename} was not generated in time")
        return False
    
    # Give the file system a moment to fully write the file
    time.sleep(2)
    
    # Check if the file is accessible and not empty
    try:
        file_size = os.path.getsize(pdf_filename)
        if file_size == 0:
            print(f"Error: PDF file {pdf_filename} is empty")
            return False
        print(f"PDF file size: {file_size} bytes")
    except Exception as e:
        print(f"Error accessing PDF file: {e}")
        return False
        
    try:
        # Create a multipart message
        msg = MIMEMultipart()
        msg['From'] = EMAIL_CONFIG["sender_email"]
        msg['To'] = ", ".join(EMAIL_CONFIG["recipients"])
        msg['Subject'] = EMAIL_CONFIG["subject"]
        
        # Create HTML body with previews of the news
        html_body = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                .article {{ margin-bottom: 20px; }}
                .title {{ color: #0066cc; }}
                .link {{ color: #0066cc; }}
            </style>
        </head>
        <body>
            <h1>AI News Report - {datetime.now().strftime('%Y-%m-%d')}</h1>
            <p>Please find attached the complete AI news report PDF. Here's a preview of the top stories:</p>
        """
        
        # Add top 3 articles as preview
        for i, article in enumerate(articles[:3]):
            title = article["title"]
            url = article["url"]
            html_body += f"""
            <div class="article">
                <h2 class="title">{i+1}. {title}</h2>
                <a href="{url}" class="link">Read the full article</a>
            </div>
            """
        
        html_body += """
            <p>The complete report is attached as a PDF.</p>
            <p>This is an automated email from your AI News Aggregator.</p>
        </body>
        </html>
        """
        
        # Attach the HTML body
        msg.attach(MIMEText(html_body, 'html'))
        
        # Attach the PDF
        with open(pdf_filename, "rb") as file:
            attachment = MIMEApplication(file.read(), _subtype="pdf")
            attachment.add_header('Content-Disposition', 'attachment', filename=pdf_filename)
            msg.attach(attachment)
        
        # Connect to SMTP server
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_CONFIG["sender_email"], EMAIL_CONFIG["sender_password"])
        
        # Send email
        server.send_message(msg)
        server.quit()
        
        print(f"Email sent successfully to {', '.join(EMAIL_CONFIG['recipients'])}")
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False

# Update the main function to include email sending
def main():
    today = datetime.now().strftime('%Y-%m-%d')
    last_week = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')

    print(f"Starting news aggregation for period {last_week} to {today}...")
    
    articles = fetch_news(start_date=last_week, end_date=today, query="Artificial Intelligence OR AI OR Machine Learning OR ML OR Deep Learning OR NLP OR Generative AI", num_articles=20)
    
    if articles:
        pdf_filename, filtered_articles = save_articles_as_pdf(articles)
        if filtered_articles:
            success = send_email(pdf_filename, filtered_articles)
            if success:
                print("Process completed successfully.")
            else:
                print("Process completed but email sending failed.")
        else:
            print("No relevant AI articles found to send.")
    else:
        print("No articles fetched or processed.")

if __name__ == "__main__":
    main()
