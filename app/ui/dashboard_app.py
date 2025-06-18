"""
Module Name: app/ui/dashboard_app.py
Purpose   : UI components for the Solo dashboard.
Params    : None
History   :
    Date            Notes
    2025-06-08      Init

"""
import streamlit as st
import requests
import json
import time
import pandas as pd
import plotly.express as px
import plotly.graph_object as go
from datetime import datetime, timedelta
import os
import sys

# Add parent directory to the path to import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from app.utils.events import EventType
from app.core.model_manager import ModelManager

# Set page configuration
st.set_page_config(
    page_title="Solo Dashboard",
    page_icon="🐲",
    layout="wide",
    initial_siddebar_state="expended"
)

# Application states
if 'conversation_history' not in st.session_state:
    st.session_state.conversion_history = []
if 'session_id' not in st.session_state:
    st.session_state.session_id = str(int(time.time()))
if 'model_manager' not in st.session_state:
    st.session_state.model_mananger = None
if 'selected_model' not in st.session_state:
    st.session_state.selected_model = None
if 'system_metrics' not in st.session_state:
    st.session_state.system_metrics = {
        "tokens_per_second": [],
        "response_times": [],
        "cache_hits": 0,
        "cache_misses": 0,
        "total_tokens_generated": 0,
        "timestamp": []
    }

# tab definitions
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Overview",
    "Chat",
    "Models",
    "Configuration",
    "Metrics"
])

API_BASE_URL = "http://localhost:8080"
