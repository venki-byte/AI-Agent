import os
import requests
from datetime import datetime, timedelta
from transformers import pipeline
import tensorflow as tf
import warnings
from hashlib import md5

# Suppress unnecessary warnings
warnings.filterwarnings("ignore")
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
tf.get_logger().setLevel('ERROR')

# Configuration for API keys
API_KEYS = {
    "newsapi": "18272c0386d242968a28372381bffd07"  # Ensure this is your valid NewsAPI key
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
def save_articles_as_text(articles):
    filtered_articles = filter_ai_articles(articles)

    if not filtered_articles:
        print("No relevant AI news found.")
        with open("news_report.txt", "w", encoding="utf-8") as file:
            file.write("No relevant AI news found.\n")
        return
    
    with open("news_report.txt", "w", encoding="utf-8") as file:
        for article in filtered_articles:
            title = article["title"]
            url = article["url"]
            content = clean_content(article.get("content", ""))
            
            # If content is too short, use description
            if len(content) < 100:
                content = clean_content(article.get("description", ""))

            if content:
                summary = summarize_text(content)
                if summary:
                    file.write(f"Title: {title}\nSummary: {summary}\nURL: {url}\n\n")
                else:
                    file.write(f"Title: {title}\nSummary: Could not summarize\nURL: {url}\n\n")
            else:
                file.write(f"Title: {title}\nSummary: No content available\nURL: {url}\n\n")
    
    print("Filtered AI news report saved successfully in 'news_report.txt'.")

# Main function to orchestrate the fetching and processing of news
def main():
    today = datetime.now().strftime('%Y-%m-%d')
    last_week = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')

    articles = fetch_news(start_date=last_week, end_date=today, query="Artificial Intelligence OR AI OR Machine Learning OR ML OR Deep Learning OR NLP OR Generative AI", num_articles=20)
    
    if articles:
        save_articles_as_text(articles)
    else:
        print("No articles fetched or processed.")

if __name__ == "__main__":
    main()