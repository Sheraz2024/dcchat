import streamlit as st
from utils.chat_history import load_chat_history, save_chat_history
from utils.chat_utils import categorize_chat_by_date
from datetime import datetime

def initialize_session_state():
    """Initialize session state variables"""
    if "history" not in st.session_state:
        loaded_history = load_chat_history()
        st.session_state.history = sorted(
            loaded_history, 
            key=lambda x: datetime.strptime(x['timestamp'], "%Y-%m-%d %H:%M:%S"), 
            reverse=True
        )
        st.session_state.current_chat_index = 0

    if "messages" not in st.session_state:
        if st.session_state.history:
            st.session_state.messages = st.session_state.history[0]["messages"]
            st.session_state.current_chat_index = 0
        else:
            st.session_state.messages = []

    if "new_chat_created" not in st.session_state:
        st.session_state.new_chat_created = False

def render_chat_history():
    """Render the chat history in the sidebar"""
    chat_categories = {
        "Today": [],
        "Yesterday": [],
        "Previous": []
    }

    for chat_index, chat in enumerate(st.session_state.history):
        category = categorize_chat_by_date(chat['timestamp'])
        chat_categories[category].append((chat_index, chat))

    for category, category_chats in chat_categories.items():
        if category_chats:
            st.subheader(category)
            for chat_index, chat in category_chats:
                first_user_question = next(
                    (msg['content'] for msg in chat["messages"] if msg['role'] == 'user'), 
                    "New Chat"
                )
                chat_title = first_user_question[:26] + '...' if len(first_user_question) > 30 else first_user_question

                col1, col2, col3 = st.columns([6, 1, 1])

                with col1:
                    if st.button(f"▶️ {chat_title}", key=f"open_{chat_index}", use_container_width=True):
                        st.session_state.messages = chat["messages"]
                        st.session_state.current_chat_index = chat_index
                        st.rerun()

                with col2:
                    if st.button("✏️", key=f"edit_{chat_index}", use_container_width=True, help="Edit this chat"):
                        st.session_state.edit_chat_index = chat_index
                        st.session_state.edit_chat_name = chat_title
                        st.session_state.show_edit_input = True
                        st.rerun()

                with col3:
                    if st.button("🗑️", key=f"delete_{chat_index}", use_container_width=True, help="Delete this chat"):
                        del st.session_state.history[chat_index]
                        save_chat_history(st.session_state.history)
                        st.rerun()

def handle_chat_input(assistant):
    """Handle user input and assistant response"""
    for msg in st.session_state.messages:
        st.chat_message(msg["role"]).write(msg["content"])

    if prompt := st.chat_input("Ask me anything about Zabbix..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.chat_message("user").write(prompt)

        with st.spinner('Thinking...'):
            response = assistant.interact(
                prompt,
                temperature=st.session_state.temperature,
                top_p=st.session_state.top_p,
                max_length=st.session_state.max_length
            )

        st.session_state.messages.append({"role": "assistant", "content": response})
        st.chat_message("assistant").write(response)

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if st.session_state.current_chat_index == -1:
            st.session_state.history.insert(0, {"timestamp": timestamp, "messages": st.session_state.messages.copy()})
            st.session_state.current_chat_index = 0
        else:
            st.session_state.history[st.session_state.current_chat_index]["messages"] = st.session_state.messages.copy()
            st.session_state.history[st.session_state.current_chat_index]["timestamp"] = timestamp

        save_chat_history(st.session_state.history)

    if "show_edit_input" in st.session_state and st.session_state.show_edit_input:
        new_name = st.text_input("Rename chat", value=st.session_state.edit_chat_name)
        if st.button("Update"):
            if new_name and new_name != st.session_state.edit_chat_name:
                st.session_state.history[st.session_state.edit_chat_index]["messages"][0]["content"] = new_name
                st.session_state.history[st.session_state.edit_chat_index]["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                save_chat_history(st.session_state.history)
                del st.session_state.show_edit_input
                st.rerun()
