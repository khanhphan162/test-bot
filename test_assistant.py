import os
import time
import logging
from datetime import datetime
from dotenv import load_dotenv
import openai

# Load environment variables
load_dotenv()

# Configuration
ASSISTANT_ID_FILE = "assistant_id.txt"
LOG_DIR = "logs"

# Setup logging
def setup_logging():
    """Setup logging configuration"""
    os.makedirs(LOG_DIR, exist_ok=True)
    log_filename = f"test_assistant_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    log_path = os.path.join(LOG_DIR, log_filename)
    
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
    print("[ERROR] OPENAI_API_KEY not set in .env file.")
    exit(1)

# Initialize OpenAI client
client = openai.OpenAI(api_key=api_key)

def load_assistant_id():
    """Load existing assistant ID"""
    if os.path.exists(ASSISTANT_ID_FILE):
        with open(ASSISTANT_ID_FILE, 'r') as f:
            return f.read().strip()
    return None

def create_thread():
    """Create a new conversation thread"""
    try:
        thread = client.beta.threads.create()
        return thread.id
    except Exception as e:
        logging.error(f"Error creating thread: {e}")
        return None

def send_message(thread_id, message):
    """Send a message to the thread"""
    try:
        client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=message
        )
        return True
    except Exception as e:
        logging.error(f"Error sending message: {e}")
        return False

def run_assistant(thread_id, assistant_id):
    """Run the assistant and get response"""
    try:
        # Create and start the run
        run = client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=assistant_id
        )
        
        # Wait for completion
        while run.status in ['queued', 'in_progress', 'cancelling']:
            time.sleep(1)
            run = client.beta.threads.runs.retrieve(
                thread_id=thread_id,
                run_id=run.id
            )
        
        if run.status == 'completed':
            # Get the messages
            messages = client.beta.threads.messages.list(
                thread_id=thread_id,
                order="desc",
                limit=1
            )
            
            if messages.data:
                # Get the assistant's response
                assistant_message = messages.data[0]
                if assistant_message.role == "assistant":
                    # Extract text content
                    content = ""
                    for content_block in assistant_message.content:
                        if content_block.type == "text":
                            content += content_block.text.value
                    return content
            
            return "No response received from assistant."
        
        elif run.status == 'failed':
            logging.error(f"Assistant run failed: {run.last_error}")
            return "Sorry, I encountered an error processing your request."
        
        else:
            logging.warning(f"Assistant run status: {run.status}")
            return "Sorry, I couldn't process your request at this time."
            
    except Exception as e:
        logging.error(f"Error running assistant: {e}")
        return "Sorry, I encountered an error processing your request."

def main():
    """Main interactive chat function"""
    # Setup logging
    log_path = setup_logging()
    
    print("=== OptiBot Assistant Test ===")
    print(f"Log file: {log_path}")
    
    # Load assistant ID
    assistant_id = load_assistant_id()
    if not assistant_id:
        print("[ERROR] No assistant ID found. Please run main.py first to create an assistant.")
        logging.error("No assistant ID found in assistant_id.txt")
        return
    
    print(f"[INFO] Using assistant: {assistant_id}")
    logging.info(f"Loaded assistant ID: {assistant_id}")
    
    # Create conversation thread
    thread_id = create_thread()
    if not thread_id:
        print("[ERROR] Failed to create conversation thread.")
        return
    
    print(f"[INFO] Created conversation thread: {thread_id}")
    logging.info(f"Created thread: {thread_id}")
    
    print("\nOptiBot is ready! Type your questions or 'quit' to exit.\n")
    
    # Interactive chat loop
    message_count = 0
    while True:
        try:
            # Get user input
            user_input = input("You: ").strip()
            
            # Check for quit command
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\nGoodbye! Thanks for testing OptiBot.")
                logging.info("User quit the session")
                break
            
            # Skip empty messages
            if not user_input:
                continue
            
            message_count += 1
            logging.info(f"User message #{message_count}: {user_input}")
            
            # Send message to assistant
            print("\nOptiBot is thinking...")
            
            if send_message(thread_id, user_input):
                # Get assistant response
                response = run_assistant(thread_id, assistant_id)
                
                # Display response
                print(f"\nOptiBot: {response}\n")
                print("-" * 50)
                
                logging.info(f"Assistant response #{message_count}: {response[:100]}{'...' if len(response) > 100 else ''}")
            else:
                print("\n[ERROR] Failed to send message. Please try again.\n")
                
        except KeyboardInterrupt:
            print("\n\nGoodbye! Thanks for testing OptiBot.")
            logging.info("User interrupted with Ctrl+C")
            break
        except Exception as e:
            print(f"\n[ERROR] Unexpected error: {e}\n")
            logging.error(f"Unexpected error in main loop: {e}")
    
    # Final summary
    print(f"\n=== Session Summary ===")
    print(f"• Messages exchanged: {message_count}")
    print(f"• Thread ID: {thread_id}")
    print(f"• Assistant ID: {assistant_id}")
    print(f"• Log saved to: {log_path}")
    
    logging.info("=== Session Summary ===")
    logging.info(f"Messages exchanged: {message_count}")
    logging.info(f"Thread ID: {thread_id}")
    logging.info(f"Assistant ID: {assistant_id}")
    logging.info(f"Session ended at: {datetime.now()}")

if __name__ == "__main__":
    main()