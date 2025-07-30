# AI Assistant

## Quick Setup

### Prerequisites
- Python 3.11+
- Docker (optional)
- OpenAI API key

### 1. Clone & Install
```bash
git clone <your-repo>
cd test-bot
pip install -r requirements.txt
```

### 2. Environment Setup
```bash
# Copy and edit environment file
cp .env.sample .env

# Add your OpenAI API key
echo "OPENAI_API_KEY=your_openai_api_key_here" >> .env
```

### 3. First Run
```bash
# Creates assistant and processes all articles
python main.py
```

## 💻 Running Locally

### Option 1: Direct Python
```bash
# Run scraper once
python main.py

# Test the assistant interactively
python test_assistant.py
```

### Option 2: Docker (One-time)
```bash
# Build and run once
docker build . -t main.py:latest
docker run -e OPENAI_API_KEY=... main.py
```

### Sample Log Output
```
[INFO] === OptiSigns Article Scraper & AI Assistant Updater ===
[INFO] Found 392 articles.
[INFO] Summary:
[INFO]   • New articles: 3
[INFO]   • Updated articles: 2  
[INFO]   • Unchanged articles: 387
[INFO] Processing 5 articles...
[INFO] • Articles processed: 5
[INFO] • Files uploaded to OpenAI: 5
[INFO] • Vector store ID: vs_xyz789
[INFO] • Assistant ID: asst_def456
[INFO] ✓ Completed at: 2024-01-15 02:00:45
```

## Assistant Playground Demo

### Example Query: "How do I add a YouTube video?"

<img width="1566" height="632" alt="result" src="https://github.com/user-attachments/assets/00f73dfa-1593-4087-9fb0-e3610e6b3588" />


## Project Structure
```
test-bot/
├── main.py                    # Main scraper & assistant creator
├── test_assistant.py          # Interactive testing tool
├── Dockerfile.simple          # One-time execution
├── requirements.txt           # Python dependencies
├── logs/                      # Run logs
├── optisigns_articles_api/    # Scraped markdown files
└── .env                       # Environment variables
```
