# main.py

import streamlit as st
from modules.zabbix_assistant import ZabbixAssistant
from sidebar.sidebar import render_sidebar, load_model_parameters
from modules.chat_handler import initialize_session_state, render_chat_history, handle_chat_input

def main():
    st.markdown("""
    <style>
        /* Set global text alignment to left */
        .css-1n76uvr, .css-2trqyj, .stButton button, .stMarkdown {
            text-align: left;
        }

        /* Style buttons for left alignment and flex layout */
        .stButton button {
            padding: 0;
            border: none;
            background-color: transparent;
            display: contents;
            align-items: center;
            text-align: left;
            font-size: 12px;
        }

        /* Ensure chat titles and icons do not wrap and align left */
        .stButton button .content {
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        /* Adjust styling for chat bubbles */
        .chat-message-bubble {
            border: none;
            margin: 0;
            padding: 0;
            font-size: 12px;
            text-align: left;
        }
    </style>
    """, unsafe_allow_html=True)

    st.title("💬 Zabbix AI Assistant")
    st.caption("🚀 Intelligent Monitoring Companion")

    initialize_session_state()

    assistant = ZabbixAssistant()
    load_model_parameters(assistant)
    render_sidebar(assistant)
    handle_chat_input(assistant)

if __name__ == "__main__":
    main()
