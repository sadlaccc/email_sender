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
    smtp_server = st.text_input("SMTP Server", value="smtp.gmail.com")
    smtp_port = st.number_input("SMTP Port", value=587, min_value=1, max_value=65535)
    smtp_user = st.text_input("SMTP Username / Email")
    smtp_password = st.text_input("App Password", type="password")

    st.markdown("---")
    st.header("Gmail Help")
    st.markdown("""
    Use **App Password** (not regular password).  
    See instructions in previous messages.
    """)

# ------------------- File Upload -------------------
uploaded_file = st.file_uploader(
    "Upload recipients file (CSV or Excel)", 
    type=["csv", "txt", "xls", "xlsx"]
)

recipients_df: Optional[pd.DataFrame] = None

if uploaded_file:
    try:
        file_ext = uploaded_file.name.lower().split(".")[-1]
        raw_data = uploaded_file.read()

        if file_ext in ["csv", "txt"]:
            recipients_df = pd.read_csv(io.StringIO(raw_data.decode("utf-8")))
        else:
            recipients_df = pd.read_excel(io.BytesIO(raw_data))

        st.write("**Original Columns Detected:**", recipients_df.columns.tolist())

        # Normalize column names
        recipients_df.columns = [str(col).strip().lower() for col in recipients_df.columns]

        # Smart detection
        email_candidates = ["email", "emails", "email address", "email_address", 
                           "mail", "to", "recipient", "recipients", "contact"]

        email_col = None
        for col in recipients_df.columns:
            if any(cand in col for cand in email_candidates):
                email_col = col
                break

        # Fallback: look for column with @ symbol
        if not email_col and len(recipients_df) > 0:
            for col in recipients_df.columns:
                if recipients_df[col].astype(str).str.contains("@").any():
                    email_col = col
                    break

        if email_col:
            recipients_df = recipients_df.rename(columns={email_col: "email"})
            st.success(f"✅ **Auto-detected** email column: `{email_col}`")
        else:
            st.error("❌ Could not auto-detect email column.")
            st.info("Please select the correct column below:")

            selected_col = st.selectbox(
                "Select the column that contains email addresses:",
                options=recipients_df.columns.tolist()
            )
            
            if st.button("✅ Confirm Email Column", type="primary"):
                recipients_df = recipients_df.rename(columns={selected_col: "email"})
                st.success(f"✅ Using **{selected_col}** as email column")
                st.rerun()

        # Show preview
        if "email" in recipients_df.columns:
            st.success(f"✅ Loaded **{len(recipients_df)}** recipients")
            st.dataframe(recipients_df.head(5), use_container_width=True)

    except Exception as e:
        st.error(f"Failed to read file: {e}")

# ------------------- Main Area -------------------
col1, col2 = st.columns([3, 1])

with col1:
    subject = st.text_input("📧 Email Subject", placeholder="Special Offer Just for You!")

    use_ai = st.checkbox("✨ Use AI to generate email body", value=False)
    # ... (AI section can stay the same)

    if "body" not in st.session_state:
        st.session_state.body = "Hello {name},\n\nThis is a personalized email.\n\nBest regards,"

    body = st.text_area("📝 Email Body (use {name} for personalization)", 
                       value=st.session_state.body, height=280, key="body")

    c1, c2, c3 = st.columns(3)
    with c1:
        dry_run = st.checkbox("Dry Run (Preview Only)", value=True)
    with c2:
        delay = st.slider("Delay between emails (sec)", 0, 5, 1)

    if st.button("🚀 Send Emails", type="primary", use_container_width=True):
        if recipients_df is None or "email" not in recipients_df.columns:
            st.error("❌ Email column not configured. Please select it above.")
        elif not smtp_user or not smtp_password:
            st.error("SMTP credentials required.")
        elif not subject.strip() or not body.strip():
            st.error("Subject and body required.")
        else:
            # Filter valid emails
            valid_df = recipients_df[recipients_df["email"].astype(str).str.contains("@", na=False)].copy()

            # ... (rest of sending code same as before)
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
                        status_text.text(f"Processing {idx+1}/{len(valid_df)}")

                        if delay > 0:
                            time.sleep(delay)

            except Exception as e:
                st.error(f"SMTP Error: {e}")

            st.success(f"✅ Sent: {sent_count} emails")
            if failed:
                st.warning(f"Failed: {len(failed)}")

with col2:
    st.markdown("### Preview")
    if recipients_df is not None and "email" in recipients_df.columns:
        st.dataframe(recipients_df[["email"]].head(8), use_container_width=True)
