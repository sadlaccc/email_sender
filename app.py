import io
import time
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

# ================== SIDEBAR ==================
with st.sidebar:
    st.header("SMTP Settings")
    smtp_server = st.text_input("SMTP Server", value="smtp.gmail.com")
    smtp_port = st.number_input("SMTP Port", value=587, min_value=1, max_value=65535)
    
    smtp_user = st.text_input("Gmail Address", placeholder="yourname@gmail.com")
    smtp_password = st.text_input("App Password (16 characters)", type="password")

    st.error("""
    ⚠️ **IMPORTANT - Gmail Authentication**
    
    You are getting error 535 because you are using your normal Gmail password.
    
    → Use an **App Password** instead.
    """)

    st.markdown("### How to Get App Password")
    st.markdown("""
    1. Go to [Google App Passwords](https://myaccount.google.com/apppasswords)
    2. Enable 2-Step Verification if not done
    3. Select **Mail** → **Other**
    4. Generate → Copy the 16-character password
    5. Paste it **without spaces** above
    """)

# ================== FILE UPLOAD ==================
uploaded_file = st.file_uploader("Upload recipients (CSV/Excel)", type=["csv", "txt", "xls", "xlsx"])

recipients_df = None

if uploaded_file:
    try:
        if uploaded_file.name.endswith(('.csv', '.txt')):
            recipients_df = pd.read_csv(uploaded_file)
        else:
            recipients_df = pd.read_excel(uploaded_file)

        # Smart email column detection
        recipients_df.columns = [str(col).strip().lower() for col in recipients_df.columns]
        
        email_col = next((col for col in recipients_df.columns if 'email' in col or 
                         recipients_df[col].astype(str).str.contains('@').any()), None)
        
        if email_col:
            recipients_df.rename(columns={email_col: 'email'}, inplace=True)
            st.success(f"✅ Email column detected: {email_col}")
        else:
            st.error("Could not detect email column. Please check your file.")
            
        st.success(f"Loaded {len(recipients_df)} recipients")
        st.dataframe(recipients_df.head(5))

    except Exception as e:
        st.error(f"File error: {e}")

# ================== MAIN AREA ==================
col1, col2 = st.columns([3, 1])

with col1:
    subject = st.text_input("Email Subject", placeholder="Special Offer Just for You!")
    
    if "body" not in st.session_state:
        st.session_state.body = "Hello {name},\n\nThis is a test email.\n\nBest regards,"

    body = st.text_area("Email Body (use {name} for personalization)", 
                       value=st.session_state.body, height=280, key="body")

    dry_run = st.checkbox("Dry Run (Don't actually send)", value=True)
    delay = st.slider("Delay between emails (seconds)", 0, 5, 1)

    if st.button("🚀 Send Emails", type="primary", use_container_width=True):
        if recipients_df is None or "email" not in recipients_df.columns:
            st.error("Please upload file and ensure email column is set.")
        elif not smtp_user or not smtp_password:
            st.error("Please enter your Gmail and App Password.")
        elif not subject or not body:
            st.error("Subject and body are required.")
        else:
            valid_df = recipients_df[recipients_df["email"].astype(str).str.contains("@")].copy()

            progress_bar = st.progress(0)
            status = st.empty()

            sent = 0
            failed = []

            try:
                with smtplib.SMTP(smtp_server, smtp_port, timeout=30) as server:
                    server.ehlo()
                    server.starttls()
                    server.ehlo()
                    server.login(smtp_user, smtp_password)

                    for idx, row in valid_df.iterrows():
                        recipient = str(row["email"]).strip()
                        name = str(row.get("name", "")).strip() or "there"

                        text = body.replace("{name}", name)

                        msg = EmailMessage()
                        msg["From"] = smtp_user
                        msg["To"] = recipient
                        msg["Subject"] = subject
                        msg.set_content(text)

                        try:
                            if not dry_run:
                                server.send_message(msg)
                            sent += 1
                        except Exception as e:
                            failed.append((recipient, str(e)))

                        progress_bar.progress((idx + 1) / len(valid_df))
                        status.text(f"Sending {idx+1}/{len(valid_df)} → {recipient}")

                        if delay > 0:
                            time.sleep(delay)

            except Exception as e:
                st.error(f"SMTP Error: {e}")
                if "535" in str(e):
                    st.error("❌ Still using wrong password. Please use **App Password** (see sidebar).")

            st.success(f"✅ Successfully sent: {sent} emails")
            if failed:
                st.warning(f"Failed: {len(failed)}")

with col2:
    st.info("**Test with Dry Run first** ✅")
