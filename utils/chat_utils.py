from datetime import datetime, timedelta
import streamlit as st

def initialize_session_state(loaded_history):
    # Sort chat history by timestamp (assuming 'loaded_history' contains a list of chat dictionaries)
    st.session_state.history = sorted(
        loaded_history,
        key=lambda x: datetime.strptime(x['timestamp'], "%Y-%m-%d %H:%M:%S"),
        reverse=True
    )
    
def categorize_chat_by_date(timestamp):
    """Categorize chat timestamp into Today, Yesterday, or Previous"""
    chat_date = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S").date()
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)

    if chat_date == today:
        return "Today"
    elif chat_date == yesterday:
        return "Yesterday"
    else:
        return "Previous"
