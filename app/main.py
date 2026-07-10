import streamlit as st
from app import db
from app.tabs import upload, review, database

st.set_page_config(page_title="Document Pipeline", layout="wide")
st.title("Document Pipeline")

if "initialized" not in st.session_state:
    db.init_db()
    st.session_state.initialized = True

tabs = st.tabs(["Upload", "Review Queue", "Database"])

with tabs[0]:
    upload.render()

with tabs[1]:
    review.render()

with tabs[2]:
    database.render()
