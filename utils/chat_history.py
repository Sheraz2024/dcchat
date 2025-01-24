import os
import csv
import json
import logging
from typing import List, Dict

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

CHAT_HISTORY_FILE = "data/chat_history.csv"

def load_chat_history() -> List[Dict]:
    """
    Load chat history from CSV file with comprehensive error handling.
    
    Returns:
        List of chat history entries
    """
    # Ensure the directory exists
    os.makedirs(os.path.dirname(CHAT_HISTORY_FILE), exist_ok=True)
    
    # If file doesn't exist or is empty, return empty list
    if not os.path.exists(CHAT_HISTORY_FILE) or os.path.getsize(CHAT_HISTORY_FILE) == 0:
        return []
    
    history = []
    try:
        with open(CHAT_HISTORY_FILE, newline='', encoding='utf-8') as file:
            csv_reader = csv.reader(file)
            
            for row_num, row in enumerate(csv_reader, 1):
                # Skip empty rows
                if not row or len(row) < 2:
                    logger.warning(f"Skipping invalid row {row_num}: {row}")
                    continue
                
                try:
                    # Safely extract timestamp and messages
                    timestamp = row[0]
                    messages_json = row[1]
                    
                    # Parse JSON messages
                    try:
                        messages = json.loads(messages_json)
                    except json.JSONDecodeError:
                        logger.error(f"Invalid JSON in row {row_num}: {messages_json}")
                        continue
                    
                    # Add to history
                    history.append({
                        "timestamp": timestamp,
                        "messages": messages
                    })
                
                except Exception as row_error:
                    logger.error(f"Error processing row {row_num}: {row_error}")
                    continue
    
    except Exception as e:
        logger.error(f"Unexpected error reading chat history: {e}")
        return []
    
    return history

def save_chat_history(history: List[Dict]):
    """
    Save chat history to CSV file with error handling.
    
    Args:
        history (List[Dict]): List of chat history entries to save
    """
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(CHAT_HISTORY_FILE), exist_ok=True)
        
        with open(CHAT_HISTORY_FILE, "w", newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            
            for chat in history:
                try:
                    # Validate and encode each entry
                    timestamp = chat.get("timestamp", "")
                    messages = chat.get("messages", [])
                    
                    # Write row with JSON-encoded messages
                    writer.writerow([
                        timestamp, 
                        json.dumps(messages)
                    ])
                
                except Exception as entry_error:
                    logger.error(f"Error saving chat entry: {entry_error}")
    
    except Exception as e:
        logger.error(f"Unexpected error saving chat history: {e}")
