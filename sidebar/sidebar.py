# sidebar/sidebar.py

import streamlit as st
from utils.chat_history import load_chat_history, save_chat_history
from modules.chat_handler import  render_chat_history

def load_model_parameters(assistant):
    """Load saved model parameters into session state"""
    params = assistant.load_params()
    if "temperature" not in st.session_state:
        st.session_state.temperature = params["temperature"]
    if "top_p" not in st.session_state:
        st.session_state.top_p = params["top_p"]
    if "max_length" not in st.session_state:
        st.session_state.max_length = params["max_length"]

def render_sidebar(assistant):
    """Render the sidebar with model selection and parameters"""
    with st.sidebar:
        available_models = assistant.get_available_models()
        if available_models:
            model_names = [model['name'] for model in available_models]

            if assistant.selected_model not in model_names:
                assistant.selected_model = model_names[0]
                assistant.save_selected_model(assistant.selected_model)

            selected_model_name = st.selectbox(
                "Select Model",
                options=model_names,
                index=model_names.index(assistant.selected_model) if assistant.selected_model else 0
            )

            selected_model = next(model for model in available_models if model['name'] == selected_model_name)

            if selected_model_name != assistant.selected_model:
                assistant.save_selected_model(selected_model_name)
                assistant.selected_model = selected_model_name

        with st.expander("⚙️ Model Parameters", expanded=False):
            st.session_state.temperature = st.slider(
                "Temperature", 0.0, 1.0, 
                st.session_state.temperature, 0.1, 
                key="temperature_slider"
            )
            st.session_state.top_p = st.slider(
                "Top P", 0.0, 1.0, 
                st.session_state.top_p, 0.1, 
                key="top_p_slider"
            )
            st.session_state.max_length = st.slider(
                "Max Length", 50, 1000, 
                st.session_state.max_length, 50, 
                key="max_length_slider"
            )

            if st.button("💾 Save Parameters"):
                assistant.save_params({
                    "temperature": st.session_state.temperature,
                    "top_p": st.session_state.top_p,
                    "max_length": st.session_state.max_length
                })

        st.markdown('<div class="centered-button">', unsafe_allow_html=True)

        if st.button("➕ Create New Chat", use_container_width=False):
            st.session_state.messages = [
                {"role": "assistant", "content": "Hello! How can I help you today?"}
            ]
            st.session_state.current_chat_index = -1
            st.session_state.new_chat_created = True
            st.rerun()

        if st.button("🧹 Clear Chat History", use_container_width=False):
            st.session_state.history = []
            st.session_state.messages = [
                {"role": "assistant", "content": "Hello! How can I help you today?"}
            ]
            save_chat_history(st.session_state.history)
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        st.header("💬 Chat History")

        render_chat_history()
