import os
import re
import time
import json
import hashlib
import requests
import logging
from datetime import datetime
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from dotenv import load_dotenv
import openai
from langchain.text_splitter import RecursiveCharacterTextSplitter

# Load environment variables
load_dotenv()

# Configuration
BASE_URL = "https://support.optisigns.com"
API_URL = f"{BASE_URL}/api/v2/help_center/en-us/articles.json"
OUTPUT_DIR = "optisigns_articles_api"
METADATA_FILE = "article_metadata.json"
VECTOR_STORE_ID_FILE = "vector_store_id.txt"
ASSISTANT_ID_FILE = "assistant_id.txt"
LOG_DIR = "logs"

# Setup logging
def setup_logging():
    """Setup logging configuration with file export"""
    os.makedirs(LOG_DIR, exist_ok=True)
    log_filename = f"optisigns_scraper_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    log_path = os.path.join(LOG_DIR, log_filename)
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='[%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler(log_path, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    return log_path

# OpenAI setup
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    logging.error("OPENAI_API_KEY not set in .env file.")
    exit(1)

# Initialize OpenAI client
client = openai.OpenAI(api_key=api_key)

# Text splitter for chunking
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1500,
    chunk_overlap=200,
    separators=["\n\n", "\n", ".", " "]
)

def slugify(text):
    """Convert text to URL-friendly slug"""
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')

def calculate_content_hash(content):
    """Calculate MD5 hash of content for change detection"""
    return hashlib.md5(content.encode('utf-8')).hexdigest()

def load_metadata():
    """Load existing article metadata"""
    if os.path.exists(METADATA_FILE):
        with open(METADATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_metadata(metadata):
    """Save article metadata"""
    with open(METADATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

def fetch_all_articles():
    """Fetch all articles from Zendesk API"""
    logging.info("Fetching articles from Zendesk API...")
    articles = []
    url = API_URL

    while url:
        try:
            res = requests.get(url, timeout=30)
            if res.status_code != 200:
                logging.error(f"Failed to fetch: {url} (Status: {res.status_code})")
                break
            data = res.json()
            articles += data.get("articles", [])
            url = data.get("next_page")
            time.sleep(0.5)  # Rate limiting
        except Exception as e:
            logging.error(f"Error fetching articles: {e}")
            break
    
    logging.info(f"Found {len(articles)} articles.")
    return articles

def clean_html_content(html_content):
    """Clean HTML content and convert to markdown"""
    # Parse HTML
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Remove unwanted tags
    for element in soup.find_all(class_=re.compile(r'(nav|ad|sidebar|footer|header)', re.I)):
        element.decompose()
    
    # Convert to markdown
    markdown = md(str(soup), heading_style="ATX")
    
    # Clean up markdown
    markdown = re.sub(r'\n{3,}', '\n\n', markdown)  # Remove excessive newlines
    markdown = markdown.strip()
    
    return markdown

def save_article(article, output_dir=OUTPUT_DIR):
    """Save article as markdown file"""
    title = article["title"]
    body_html = article["body"]
    article_url = f"{BASE_URL}/hc/en-us/articles/{article['id']}"
    
    # Clean and convert content
    markdown_content = clean_html_content(body_html)
    
    # Create full content with metadata
    full_content = f"# {title}\n\n"
    full_content += f"**Article URL:** {article_url}\n\n"
    full_content += f"**Last Updated:** {article.get('updated_at', 'Unknown')}\n\n"
    full_content += markdown_content
    
    # Save file
    slug = slugify(title)
    os.makedirs(output_dir, exist_ok=True)
    file_path = os.path.join(output_dir, f"{slug}.md")
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(full_content)
    
    return file_path, calculate_content_hash(full_content)

def detect_changes(articles):
    """Detect new, updated, and unchanged articles"""
    metadata = load_metadata()
    new_articles = []
    updated_articles = []
    unchanged_articles = []
    
    for article in articles:
        article_id = str(article['id'])
        title = article['title']
        updated_at = article.get('updated_at')
        
        # Create temporary content to check hash
        body_html = article["body"]
        article_url = f"{BASE_URL}/hc/en-us/articles/{article['id']}"
        markdown_content = clean_html_content(body_html)
        full_content = f"# {title}\n\n"
        full_content += f"**Article URL:** {article_url}\n\n"
        full_content += f"**Last Updated:** {updated_at}\n\n"
        full_content += markdown_content
        current_hash = calculate_content_hash(full_content)
        
        if article_id not in metadata:
            new_articles.append(article)
        elif metadata[article_id].get('hash') != current_hash:
            updated_articles.append(article)
        else:
            unchanged_articles.append(article)
    
    return new_articles, updated_articles, unchanged_articles

def upload_file_to_openai(file_path):
    """Upload a file to OpenAI"""
    try:
        with open(file_path, "rb") as f:
            file_obj = client.files.create(file=f, purpose="assistants")
        return file_obj.id
    except Exception as e:
        logging.error(f"Error uploading {file_path}: {e}")
        return None

def create_or_update_vector_store(file_ids, vector_store_id=None):
    """Create new vector store or update existing one"""
    try:
        if vector_store_id:
            # Update existing vector store
            logging.info(f"Updating existing vector store: {vector_store_id}")
            # Add files to existing vector store
            for file_id in file_ids:
                client.vector_stores.files.create(
                    vector_store_id=vector_store_id,
                    file_id=file_id
                )
            return vector_store_id
        else:
            # Create new vector store
            logging.info("Creating new vector store...")
            vector_store = client.vector_stores.create(
                name="OptiSigns Knowledge Base"
            )
            # Add files to the vector store
            for file_id in file_ids:
                client.vector_stores.files.create(
                    vector_store_id=vector_store.id,
                    file_id=file_id
                )
            return vector_store.id
    except Exception as e:
        logging.error(f"Error with vector store: {e}")
        return None

def create_assistant(vector_store_id):
    """Create OpenAI assistant with the specified system prompt"""
    system_prompt = """You are OptiBot, the customer-support bot for OptiSigns.com.
• Tone: helpful, factual, concise.
• Only answer using the uploaded docs.
• Max 5 bullet points; else link to the doc.
• Cite up to 3 "Article URL:" lines per reply."""
    
    try:
        assistant = client.beta.assistants.create(
            name="OptiBot - OptiSigns Support Assistant",
            instructions=system_prompt,
            model="gpt-4o-mini",
            tools=[{"type": "file_search"}],
            tool_resources={
                "file_search": {
                    "vector_store_ids": [vector_store_id]
                }
            }
        )
        return assistant.id
    except Exception as e:
        logging.error(f"Error creating assistant: {e}")
        return None

def load_vector_store_id():
    """Load existing vector store ID"""
    if os.path.exists(VECTOR_STORE_ID_FILE):
        with open(VECTOR_STORE_ID_FILE, 'r') as f:
            return f.read().strip()
    return None

def save_vector_store_id(vector_store_id):
    """Save vector store ID"""
    with open(VECTOR_STORE_ID_FILE, 'w') as f:
        f.write(vector_store_id)

def load_assistant_id():
    """Load existing assistant ID"""
    if os.path.exists(ASSISTANT_ID_FILE):
        with open(ASSISTANT_ID_FILE, 'r') as f:
            return f.read().strip()
    return None

def save_assistant_id(assistant_id):
    """Save assistant ID"""
    with open(ASSISTANT_ID_FILE, 'w') as f:
        f.write(assistant_id)

def calculate_chunking_stats(articles):
    """Calculate chunking statistics"""
    total_chunks = 0
    chunk_details = []
    
    for article in articles:
        title = article['title']
        body_html = article['body']
        markdown_content = clean_html_content(body_html)
        chunks = text_splitter.split_text(markdown_content)
        chunk_count = len(chunks)
        total_chunks += chunk_count
        
        chunk_details.append({
            'title': title,
            'chunk_count': chunk_count,
            'content_length': len(markdown_content)
        })
    
    return total_chunks, chunk_details

def main():
    """Main function to run the scraper and uploader"""
    # Setup logging
    log_path = setup_logging()
    
    logging.info("=== OptiSigns Article Scraper & AI Assistant Updater ===")
    logging.info(f"Started at: {datetime.now()}")
    logging.info(f"Log file: {log_path}")
    
    # Fetch all articles
    articles = fetch_all_articles()
    if not articles:
        logging.error("No articles found. Exiting.")
        return
    
    # Detect changes
    logging.info("Detecting changes...")
    new_articles, updated_articles, unchanged_articles = detect_changes(articles)
    
    logging.info("Summary:")
    logging.info(f"• New articles: {len(new_articles)}")
    logging.info(f"• Updated articles: {len(updated_articles)}")
    logging.info(f"• Unchanged articles: {len(unchanged_articles)}")

    # Process only new and updated articles
    articles_to_process = new_articles + updated_articles

    if not articles_to_process:
        logging.info("No changes detected. Nothing to update.")
        return
    
    logging.info(f"Processing {len(articles_to_process)} articles...")
    
    # Save articles and collect file info
    metadata = load_metadata()
    uploaded_file_ids = []
    
    for article in articles_to_process:
        try:
            file_path, content_hash = save_article(article)
            logging.info(f"Saved: {os.path.basename(file_path)}")
            
            # Upload to OpenAI
            file_id = upload_file_to_openai(file_path)
            if file_id:
                uploaded_file_ids.append(file_id)
                logging.info(f"Uploaded to OpenAI: {file_id}")
                
                # Update metadata
                article_id = str(article['id'])
                metadata[article_id] = {
                    'title': article['title'],
                    'hash': content_hash,
                    'updated_at': article.get('updated_at'),
                    'file_id': file_id,
                    'processed_at': datetime.now().isoformat()
                }
            
            time.sleep(0.5)  # Rate limiting
        except Exception as e:
            logging.error(f"Error processing article {article.get('title', 'Unknown')}: {e}")
    
    # Update vector store
    if uploaded_file_ids:
        logging.info(f"Updating vector store with {len(uploaded_file_ids)} files...")
        
        vector_store_id = load_vector_store_id()
        new_vector_store_id = create_or_update_vector_store(uploaded_file_ids, vector_store_id)
        
        if new_vector_store_id:
            save_vector_store_id(new_vector_store_id)
            logging.info(f"Vector store updated: {new_vector_store_id}")
            
            # Create or update assistant
            assistant_id = load_assistant_id()
            if not assistant_id:
                logging.info("Creating new assistant...")
                assistant_id = create_assistant(new_vector_store_id)
                if assistant_id:
                    save_assistant_id(assistant_id)
                    logging.info(f"Assistant created: {assistant_id}")
            else:
                logging.info(f"Using existing assistant: {assistant_id}")
    
    # Save updated metadata
    save_metadata(metadata)
    
    # Calculate chunking statistics
    total_chunks, chunk_details = calculate_chunking_stats(articles)
    
    # Log final summary
    logging.info("=== Final Summary ===")
    logging.info(f"• Articles processed: {len(articles_to_process)}")
    logging.info(f"• Files uploaded to OpenAI: {len(uploaded_file_ids)}")
    logging.info(f"• Vector store ID: {load_vector_store_id()}")
    logging.info(f"• Assistant ID: {load_assistant_id()}")
    logging.info(f"• Total estimated chunks: {total_chunks}")
    logging.info(f"• Chunking strategy: RecursiveCharacterTextSplitter (chunk_size=1500, overlap=200)")
    logging.info(f"• Separators: ['\\n\\n', '\\n', '.', ' ']")
    logging.info(f"• Completed at: {datetime.now()}")
    logging.info(f"• Log saved to: {log_path}")

    # # Log detailed chunking breakdown
    # logging.info("=== Chunking Details ===")
    # for detail in chunk_details[:10]:
    #     logging.info(f"• {detail['title']}: {detail['chunk_count']} chunks ({detail['content_length']} chars)")
    
    # if len(chunk_details) > 10:
    #     logging.info(f"• ... and {len(chunk_details) - 10} more articles")

if __name__ == "__main__":
    main()