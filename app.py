import io
import time
import socket
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

st.title("✉️ Bulk Email Sender - Any Provider")

# ================== SIDEBAR ==================
with st.sidebar:
    st.header("SMTP Configuration")
    
    provider = st.selectbox(
        "Select Provider",
        ["Custom", "Gmail", "Outlook", "Yahoo", "Zoho", "GMX", "Other"],
        index=0
    )
    
    # Preset servers
    presets = {
        "Gmail": ("smtp.gmail.com", 587),
        "Outlook": ("smtp.office365.com", 587),
        "Yahoo": ("smtp.mail.yahoo.com", 587),
        "Zoho": ("smtp.zoho.com", 587),
        "GMX": ("mail.gmx.com", 587)
    }
    
    if provider in presets:
        default_server, default_port = presets[provider]
    else:
        default_server = "smtp.yourdomain.com"
        default_port = 587

    smtp_server = st.text_input("SMTP Server Hostname", value=default_server, 
                               help="Example: smtp.gmail.com")
    smtp_port = st.number_input("Port", value=default_port, min_value=1, max_value=65535)

    smtp_user = st.text_input("Email Address / Username")
    smtp_password = st.text_input("Password / App Password", type="password")

    st.markdown("---")
    st.info("**Common SMTP Servers**")
    st.markdown("""
    • Gmail → `smtp.gmail.com` (587)  
    • Outlook → `smtp.office365.com` (587)  
    • Yahoo → `smtp.mail.yahoo.com` (587)
    """)

# ================== FILE UPLOAD ==================
uploaded_file = st.file_uploader("Upload recipients (CSV or Excel)", type=["csv", "txt", "xls", "xlsx"])

recipients_df: Optional[pd.DataFrame] = None

if uploaded_file:
    try:
        if uploaded_file.name.lower().endswith(('.csv', '.txt')):
            recipients_df = pd.read_csv(uploaded_file)
        else:
            recipients_df = pd.read_excel(uploaded_file)

        recipients_df.columns = [str(col).strip().lower() for col in recipients_df.columns]

        # Smart email column detection
        email_col = next((col for col in recipients_df.columns if any(x in col for x in ["email", "mail", "to"])), None)
        if not email_col and len(recipients_df) > 0:
            for col in recipients_df.columns:
                if recipients_df[col].astype(str).str.contains("@").any():
                    email_col = col
                    break

        if email_col:
            recipients_df = recipients_df.rename(columns={email_col: "email"})
            st.success(f"✅ Email column detected: **{email_col}**")
        else:
            st.error("Could not detect email column.")
            selected = st.selectbox("Choose email column:", recipients_df.columns)
            if st.button("Confirm Email Column"):
                recipients_df.rename(columns={selected: "email"}, inplace=True)
                st.rerun()

        st.success(f"✅ Loaded {len(recipients_df)} recipients")
        st.dataframe(recipients_df.head(5), use_container_width=True)

    except Exception as e:
        st.error(f"File error: {e}")

# ================== MAIN AREA ==================
col1, col2 = st.columns([3, 1])

with col1:
    subject = st.text_input("📧 Email Subject", placeholder="Hello from Our Team!")

    if "body" not in st.session_state:
        st.session_state.body = "Hello {name},\n\nThis is a test message.\n\nBest regards,"

    body = st.text_area("📝 Email Body (use {name} for personalization)", 
                       value=st.session_state.body, height=280, key="body")

    c1, c2, c3 = st.columns(3)
    with c1:
        dry_run = st.checkbox("🔍 Dry Run (Don't send)", value=True)
    with c2:
        delay = st.slider("Delay (seconds)", 0, 5, 1)

    if st.button("🚀 Send Emails", type="primary", use_container_width=True):
        if recipients_df is None or "email" not in recipients_df.columns:
            st.error("Please upload file and set email column.")
        elif not smtp_user or not smtp_password:
            st.error("Email and password required.")
        elif not subject.strip() or not body.strip():
            st.error("Subject and body required.")
        else:
            # DNS / Connection Pre-check
            try:
                socket.gethostbyname(smtp_server)
            except socket.gaierror:
                st.error(f"❌ Cannot resolve hostname: **{smtp_server}**")
                st.info("Check spelling or your internet connection.")
                st.stop()

            valid_df = recipients_df[recipients_df["email"].astype(str).str.contains("@", na=False)].copy()

            progress_bar = st.progress(0)
            status_text = st.empty()

            sent_count = 0
            failed = []

            try:
                with smtplib.SMTP(smtp_server, smtp_port, timeout=20) as smtp:
                    smtp.ehlo()
                    if smtp_port in (587, 25):
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
                if "Name or service not known" in str(e):
                    st.error(f"**Hostname not found**: `{smtp_server}`")
                    st.info("Double-check the SMTP server address.")

            st.success(f"✅ Sent **{sent_count}** emails")
            if failed:
                st.warning(f"Failed: {len(failed)}")
                with st.expander("Failures"):
                    for email, err in failed:
                        st.write(f"{email} → {err}")

with col2:
    st.info("**Start with Dry Run enabled** to test your SMTP settings safely.")
