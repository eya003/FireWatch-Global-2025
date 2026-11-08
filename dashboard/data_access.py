"""Cached access to validated source exports for Streamlit pages."""

import streamlit as st

from dashboard.data import load_fire_data


@st.cache_data(show_spinner="Loading and validating the 2025 exports…")
def get_fire_data():
    return load_fire_data()
