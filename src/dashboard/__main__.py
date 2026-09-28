"""CLI entry point: python -m src.dashboard

Starts the Gleipnir Streamlit dashboard.
Equivalent to: streamlit run src/dashboard/app.py
"""

from src.dashboard import launch_dashboard

launch_dashboard(block=True)
