@echo off
cd /d "%~dp0"
python -m streamlit run app.py --server.port 8501
