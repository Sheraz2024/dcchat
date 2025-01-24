import os
import re
import logging
import json
import csv
from dotenv import load_dotenv
from pyzabbix import ZabbixAPI
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import trim_messages
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import Annotated, TypedDict
from modules.zabbix_tools import initialize_zabbix_tools
from typing import List, Sequence, Dict
import streamlit as st

# Constants
CHAT_HISTORY_FILE = "chat_history.csv"
PARAMS_FILE = 'settings/model_params.json'
MODEL_FILE = 'settings/model.json'
SELECTED_MODEL_FILE = 'settings/selected_model.json' 
# Zabbix Assistant Class
class ZabbixAssistant:
    def __init__(self):
        self._load_environment()
        self._initialize_logging()
        self._initialize_zabbix()
        self.selected_model = self.load_selected_model()
        self._initialize_llm()
        self.tools = initialize_zabbix_tools(self.zabbix)
        self.models = self.load_models()
        self.selected_model = self.load_selected_model()
        self.system_message = self._create_system_message()
        self.prompt = self._create_prompt()
        self.workflow = self._create_workflow()

    def _load_environment(self):
        load_dotenv()

    def _initialize_logging(self):
        logging.basicConfig(
            level=logging.ERROR, 
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            filename='logs/zabbix_assistant.log'
        )

    def _initialize_zabbix(self):
        try:
            self.zabbix = ZabbixAPI(os.getenv("ZABBIX_API_URL"))
            self.zabbix.login(os.getenv("ZABBIX_USER"), os.getenv("ZABBIX_PASSWORD"))
            logging.info("Zabbix API connection successful")
        except Exception as e:
            self.zabbix = None
            logging.error(f"Zabbix API connection failed: {e}")

    def _initialize_llm(self):
        if not self.selected_model:
            logging.error("No model selected. Defaulting to a fallback model.")
            self.selected_model = "gpt-3.5-turbo"

        self.llm = ChatOpenAI(
            model=self.selected_model,
            temperature=0.7,
            api_key=os.getenv("OPENAI_API_KEY")
        )

    def _create_system_message(self):
        return SystemMessage(content="""\
        You are a helpful AI assistant specializing in Zabbix monitoring. 
        Use the available tools to provide precise information about Zabbix infrastructure.
        If a query cannot be answered by tools, provide a helpful general response.
        """)

    def _create_prompt(self):
        return ChatPromptTemplate.from_messages([
            self.system_message, 
            MessagesPlaceholder(variable_name="messages")
        ])

    def _create_workflow(self):
        class State(TypedDict):
            messages: Annotated[Sequence[BaseMessage], add_messages]
            language: str

        workflow = StateGraph(state_schema=State)
        workflow.add_node("chatbot_agent", self.chatbot_agent)
        workflow.add_edge(START, "chatbot_agent")
        workflow.add_edge("chatbot_agent", END)

        memory_saver = MemorySaver()
        return workflow.compile(checkpointer=memory_saver)

    def _trim_conversation_messages(self, messages: Sequence[BaseMessage], max_tokens: int = 3000) -> List[BaseMessage]:
        try:
            trimmed_messages = trim_messages(
                max_tokens=max_tokens,
                strategy="last",
                token_counter=self.llm,
                include_system=True,
                allow_partial=False,
                start_on="human"
            ).invoke(messages)
            return trimmed_messages
        except Exception as e:
            logging.warning(f"Token trimming failed: {e}. Falling back to last few messages.")
            return list(messages)[-5:]

    def chatbot_agent(self, state: dict):
        trimmed_messages = self._trim_conversation_messages(state["messages"])
        user_query = trimmed_messages[-1].content

        try:
            # Few-Shot Examples for Zabbix API Response Interpretation
            few_shot_examples = [
                {
                    "query": "Show me the status of hosts",
                    "api_response": """
                    Host: web-server-01 (ID: 10001, Status: Enabled)
                    Host: database-server-02 (ID: 10002, Status: Disabled)
                    Host: app-server-03 (ID: 10003, Status: Enabled)
                    """,
                    "interpretation": """
                    I've analyzed the host statuses for you:
                    1. web-server-01 is currently operational and ready to handle requests.
                    2. database-server-02 is currently offline or disabled. This might require immediate attention.
                    3. app-server-03 is active and functioning normally.

                    Recommendation: Investigate why the database server is disabled and take necessary actions to restore its functionality.
                    """
                },
                {
                    "query": "Get triggers with high severity",
                    "api_response": """
                    Trigger: High CPU Usage on Production Server
                    ID: 20001
                    Priority: High
                    Status: Enabled
                    Current State: Problem

                    Trigger: Memory Leak Detected
                    ID: 20002
                    Priority: Disaster
                    Status: Enabled
                    Current State: Problem
                    """,
                    "interpretation": """
                    Critical Alerts Detected:
                    1. High CPU Usage on Production Server (High Severity)
                    - This trigger indicates potential performance bottlenecks
                    - Immediate investigation is recommended to prevent service disruption

                    2. Memory Leak Detected (Disaster Severity)
                    - Severe memory management issue detected
                    - Urgent action required to prevent system instability
                    - Potential root causes: application memory leaks, insufficient memory allocation

                    Recommended Actions:
                    - Conduct immediate performance analysis
                    - Check application logs
                    - Consider scaling resources or optimizing application code
                    """
                }
            ]

            # First, determine if the query is Zabbix-related
            tool_selection = self._select_tool(trimmed_messages)
            logging.info(f"LLM Tool Selection: {tool_selection}")

            # If a Zabbix tool is selected
            matched_tools = self._match_tools(tool_selection)
            if matched_tools:
                # Execute the selected tool
                tool_response = self._run_tool(matched_tools[0], user_query)
                logging.info(f"Tool Response: {tool_response}")

                # Create a few-shot prompting template
                few_shot_prompt = ChatPromptTemplate.from_messages([
                    SystemMessage(content="""
                    You are an expert Zabbix monitoring data interpreter.
                    Your task is to transform raw Zabbix API data into actionable, human-readable insights.

                    Guidelines:
                    - Provide clear, concise explanations
                    - Highlight critical information
                    - Offer potential recommendations
                    - Use a professional, informative tone
                    """),
                    # Add few-shot examples
                    *[
                        HumanMessage(content=f"Query: {example['query']}\nAPI Response: {example['api_response']}")
                        for example in few_shot_examples
                    ],
                    *[
                        AIMessage(content=example['interpretation'])
                        for example in few_shot_examples
                    ],
                    # Current query and response
                    HumanMessage(content=f"Query: {user_query}\nAPI Response: {tool_response}")
                ])

                # Create a chain to interpret the response using few-shot learning
                interpretation_chain = (
                    few_shot_prompt 
                    | self.llm 
                    | StrOutputParser()
                )

                # Generate an interpreted response
                interpreted_response = interpretation_chain.invoke({})
                
                return {"messages": [AIMessage(content=interpreted_response)]}

            # If no Zabbix tool is selected, use default response
            return self._default_response(trimmed_messages)

        except Exception as e:
            logging.error(f"Error in tool selection and interpretation: {e}")
            return {"messages": [AIMessage(content="I encountered an unexpected error processing your request.")]}
    
    def _select_tool(self, trimmed_messages):
        tool_descriptions = "\n".join([f"- {tool.name}: {tool.description}" for tool in self.tools])
        tool_selection_prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content=f"""
            You are an expert at identifying the most appropriate Zabbix tool for a given query.

            Available Tools:
            {tool_descriptions}

            Your task:
            1. Carefully analyze the user's query
            2. Select the MOST RELEVANT tool based on its description
            3. Respond STRICTLY with:
            - EXACT tool name if Zabbix-related
            - "GENERAL" for non-Zabbix queries

            Matching Guidelines:
            - Be precise in tool selection
            - Consider tool description carefully
            - If unsure, default to most generic matching tool
            """),
            MessagesPlaceholder(variable_name="messages")
        ])
        tool_selection_chain = tool_selection_prompt | self.llm | StrOutputParser()
        return tool_selection_chain.invoke({"messages": trimmed_messages})

    def _match_tools(self, tool_selection):
        return [tool for tool in self.tools if tool.name.lower() in tool_selection.lower()]

    def _execute_tool(self, matched_tool, user_query):
        logging.info(f"Selected Tool: {matched_tool.name}")
        try:
            tool_response = self._run_tool(matched_tool, user_query)
            logging.info(f"Tool Response: {tool_response}")
            return {"messages": [AIMessage(content=tool_response)]}
        except Exception as e:
            logging.error(f"Error executing tool {matched_tool.name}: {e}")
            return {"messages": [AIMessage(content=f"I encountered an error with the {matched_tool.name} tool.")]}

    def _run_tool(self, matched_tool, user_query):
        parameter_tools = {
            "Get Hosts": lambda: matched_tool.func(limit=self._extract_limit(user_query)),
            "Get Triggers": lambda: matched_tool.func(
                limit=self._extract_limit(user_query), 
                severity=self._extract_severity(user_query)
            )
        }

        if matched_tool.name in parameter_tools:
            return parameter_tools[matched_tool.name]()
        return matched_tool.func()

    def _default_response(self, trimmed_messages):
        chain = (
            RunnablePassthrough() 
            | self.prompt 
            | self.llm 
            | StrOutputParser()
        )
        response = chain.invoke({"messages": trimmed_messages})
        return {"messages": [AIMessage(content=response)]}

    def _extract_limit(self, query):
        limit_match = re.search(r'(\d+)\s*(hosts?|triggers?|items?)', query.lower())
        return int(limit_match.group(1)) if limit_match else None

    def _extract_severity(self, query):
        severity_map = {
            'not classified': 'not_classified',
            'information': 'information',
            'warning': 'warning',
            'average': 'average',
            'high': 'high',
            'disaster': 'disaster'
        }
        query = query.lower()
        for severity, mapped_severity in severity_map.items():
            if severity in query:
                return [mapped_severity]
        return None

    def interact(self, user_input: str, temperature: float = 0.7, top_p: float = 1.0, max_length: int = 300):
        config = {"configurable": {"thread_id": "zabbix_assistant_thread"}}
        selected_model = self.selected_model

        if not selected_model:
            logging.error("No model selected.")
            return "No model selected. Please choose a model."

        # Update the LLM settings dynamically based on user input
        self.llm.model_name = selected_model
        self.llm.temperature = temperature
        self.llm.top_p = top_p
        self.llm.max_tokens = max_length

        payload = {"messages": [HumanMessage(content=user_input)], "language": "English"}

        try:
            for event in self.workflow.stream(payload, config):
                for value in event.values():
                    if isinstance(value.get('messages', [])[-1], AIMessage):
                        return value['messages'][-1].content
        except Exception as e:
            logging.error(f"Error in interaction: {e}")
            return f"An error occurred: {e}"

    # Chat History Functions
    def load_chat_history():
        if not os.path.exists(CHAT_HISTORY_FILE):
            return []
        history = []
        with open(CHAT_HISTORY_FILE, newline='', encoding='utf-8') as file:
            reader = csv.reader(file)
            for row in reader:
                history.append({"timestamp": row[0], "messages": json.loads(row[1])})
        return history

    def save_chat_history(history):
        with open(CHAT_HISTORY_FILE, "w", newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            for chat in history:
                writer.writerow([chat["timestamp"], json.dumps(chat["messages"])])
    
    def load_params(self):
        try:
            with open(PARAMS_FILE, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {"temperature": 0.7, "top_p": 1.0, "max_length": 3000}

    # Save parameters to JSON file
    def save_params(self, params):
        with open(PARAMS_FILE, 'w') as f:
            json.dump(params, f)

    def load_models(self):
        model_file = os.path.join("settings", "model.json")
        if os.path.exists(model_file):
            try:
                with open(model_file, "r") as file:
                    models = json.load(file)
                return models.get('models', [])
            except json.JSONDecodeError as e:
                logging.error(f"Error decoding JSON from {model_file}: {e}")
                return []
        else:
            logging.error(f"Model file {model_file} not found.")
            return []

    def load_selected_model(self):
        """Load the currently selected model from session state or from file."""
        # First, check the session state for a selected model
        if "selected_model" in st.session_state:
            return st.session_state.selected_model

        # If not in session state, load from the JSON file
        if os.path.exists(SELECTED_MODEL_FILE):
            try:
                with open(SELECTED_MODEL_FILE, "r") as file:
                    selected_model_data = json.load(file)
                    return selected_model_data.get("model", None)
            except json.JSONDecodeError as e:
                logging.error(f"Error decoding JSON from {SELECTED_MODEL_FILE}: {e}")
                return None

        # If no selected model found, return the first model or None
        return self.models[0]["name"] if self.models else None

    def save_selected_model(self, model_name):
        """Save the selected model to session state and a JSON file."""
        st.session_state.selected_model = model_name

        # Save to the JSON file
        with open(SELECTED_MODEL_FILE, "w") as file:
            json.dump({"model": model_name}, file)

    def get_available_models(self):
        """Return the available models"""
        return self.models

    