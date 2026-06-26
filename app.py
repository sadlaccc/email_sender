import io
import time
import os
import smtplib
from email.message import EmailMessage
from typing import List, Tuple, Optional

import pandas as pd
import streamlit as st

try:
    from openai import OpenAI
    openai_available = True
except ImportError:
    openai_available = False

st.set_page_config(page_title="Bulk Email Sender", page_icon="✉️", layout="wide")

st.title("✉️ Bulk Email Sender")
st.markdown("Upload your recipient list and send personalized bulk emails.")

# ------------------- Sidebar -------------------
with st.sidebar:
    st.header("SMTP Settings")
    smtp_server = st.text_input("SMTP Server", value="smtp.gmail.com", help="For Gmail: smtp.gmail.com")
    smtp_port = st.number_input("SMTP Port", value=587, min_value=1, max_value=65535)
    
    smtp_user = st.text_input("SMTP Username / Email", help="Your full Gmail address")
    smtp_password = st.text_input("SMTP Password / App Password", type="password")

    st.markdown("---")
    st.warning("""
    **Gmail Users Important**
    - Do **NOT** use your normal Gmail password
    - Use an **App Password** instead
    - See instructions below
    """)

    st.markdown("### How to Generate App Password")
    st.markdown("""
    1. Enable 2-Step Verification in your Google Account
    2. Go to [App passwords](https://myaccount.google.com/apppasswords)
    3. Select **Mail** → **Other**
    4. Generate and copy the 16-character password
    """)

    st.markdown("---")
    st.header("AI Assistance")
    openai_api_key = st.text_input("OpenAI API Key", type="password")

# File upload and rest of the code remains the same as previous version...

# ------------------- File Upload -------------------
uploaded_file = st.file_uploader("Upload recipients file (CSV or Excel)", type=["csv", "txt", "xls", "xlsx"])

recipients_df: Optional[pd.DataFrame] = None

if uploaded_file:
    # ... (keep your existing file reading + smart column detection code here)
    pass  # I'll keep it short — use the file handling from previous response

# ------------------- Main UI -------------------
col1, col2 = st.columns([3, 1])

with col1:
    subject = st.text_input("📧 Email Subject", placeholder="Special Offer for You!")

    # AI Section (keep as before)
    use_ai = st.checkbox("✨ Use AI to generate email body", value=False)
    # ... AI code ...

    if "body" not in st.session_state:
        st.session_state.body = "Hello {name},\n\nThis is a personalized message.\n\nBest regards,"

    body = st.text_area("📝 Email Body", value=st.session_state.body, height=280, key="body")

    c1, c2, c3 = st.columns(3)
    with c1:
        dry_run = st.checkbox("Dry Run (Preview Only)", value=True)
    with c2:
        delay = st.slider("Delay between emails (sec)", 0, 5, 1)

    if st.button("🚀 Send Emails", type="primary", use_container_width=True):
        if recipients_df is None or "email" not in recipients_df.columns:
            st.error("Email column not configured.")
        elif not smtp_user or not smtp_password:
            st.error("Please fill in SMTP credentials.")
        elif not subject.strip() or not body.strip():
            st.error("Subject and body are required.")
        else:
            valid_df = recipients_df[recipients_df["email"].astype(str).str.contains("@", na=False)].copy()

            progress_bar = st.progress(0)
            status_text = st.empty()

            sent_count = 0
            failed = []

            try:
                with smtplib.SMTP(smtp_server, smtp_port, timeout=30) as smtp:
                    smtp.ehlo()
                    if smtp_port == 587:
                        smtp.starttls()
                        smtp.ehlo()
                    smtp.login(smtp_user, smtp_password)

                    for idx, row in valid_df.iterrows():
                        recipient = str(row["email"]).strip()
                        name = str(row.get("name", "")).strip() or "there"

                        personalized = body.replace("{name}", name)

                        msg = EmailMessage()
                        msg["From"] = smtp_user
                        msg["To"] = recipient
                        msg["Subject"] = subject
                        msg.set_content(personalized)

                        try:
                            if not dry_run:
                                smtp.send_message(msg)
                            sent_count += 1
                        except Exception as e:
                            failed.append((recipient, str(e)))

                        progress_bar.progress((idx + 1) / len(valid_df))
                        status_text.text(f"Processing {idx+1}/{len(valid_df)} → {recipient}")

                        if delay > 0:
                            time.sleep(delay)

            except Exception as e:
                st.error(f"SMTP Error: {e}")
                if "535" in str(e):
                    st.error("**Gmail rejected credentials** — Please use an **App Password** (see sidebar)")

            st.success(f"✅ Sent **{sent_count}** emails successfully!")
            if failed:
                st.warning(f"Failed: {len(failed)}")
                with st.expander("Failures"):
                    for email, err in failed:
                        st.write(f"{email}: {err}")

with col2:
    if recipients_df is not None:
        st.metric("Total Recipients", len(recipients_df))
        st.dataframe(recipients_df.head(6), use_container_width=True)
