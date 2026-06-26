import io
import time
import re
import os
import smtplib  # ← This was missing!
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
    smtp_password = st.text_input("SMTP Password / App Password", type="password")

    st.markdown("---")
    st.header("AI Assistance")
    openai_api_key = st.text_input("OpenAI API Key", type="password")

# ------------------- File Upload & Smart Email Detection -------------------
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
            try:
                recipients_df = pd.read_csv(io.StringIO(raw_data.decode("utf-8")))
            except UnicodeDecodeError:
                recipients_df = pd.read_csv(io.StringIO(raw_data.decode("latin-1")))
        else:
            try:
                recipients_df = pd.read_excel(io.BytesIO(raw_data))
            except ImportError:
                st.error("❌ Missing openpyxl. Run: `pip install openpyxl`")
                st.stop()

        # Normalize columns
        original_cols = recipients_df.columns.tolist()
        recipients_df.columns = [str(col).strip().lower() for col in original_cols]

        # Smart email column detection
        email_candidates = ["email", "emails", "email address", "email_address", 
                           "mail", "to", "recipient", "recipients", "contact"]
        
        email_col = None
        for col in recipients_df.columns:
            if any(cand in col for cand in email_candidates):
                email_col = col
                break

        # Fallback: first column containing '@'
        if not email_col and len(recipients_df) > 0:
            for col in recipients_df.columns:
                if recipients_df[col].astype(str).str.contains("@").any():
                    email_col = col
                    break

        if email_col:
            recipients_df = recipients_df.rename(columns={email_col: "email"})
            st.success(f"✅ Detected & using **{email_col}** as email column")
        else:
            st.warning("Could not auto-detect email column.")
            selected = st.selectbox("Select email column:", options=original_cols)
            if st.button("Confirm Column"):
                recipients_df = recipients_df.rename(columns={selected.lower(): "email"})
                st.success(f"✅ Using **{selected}**")
                st.rerun()

        st.success(f"✅ Loaded **{len(recipients_df)}** rows")

    except Exception as e:
        st.error(f"Failed to read file: {e}")

# ------------------- Main Interface -------------------
col1, col2 = st.columns([3, 1])

with col1:
    subject = st.text_input("📧 Email Subject", placeholder="Special Offer Just for You!")

    use_ai = st.checkbox("✨ Use AI to generate email body", value=False)

    if use_ai and openai_available:
        ai_prompt = st.text_area(
            "AI Instructions", 
            value="Write a friendly, professional bulk email with a clear call to action.",
            height=100
        )
        if st.button("Generate Draft with AI", type="primary"):
            if not (openai_api_key or os.getenv("OPENAI_API_KEY")):
                st.error("Please add OpenAI API key in sidebar.")
            else:
                try:
                    client = OpenAI(api_key=openai_api_key or os.getenv("OPENAI_API_KEY"))
                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": "Expert email copywriter"},
                            {"role": "user", "content": f"Subject: {subject}\nInstructions: {ai_prompt}\nUse {{name}} for personalization. Output only the body."}
                        ],
                        temperature=0.7
                    )
                    body_text = response.choices[0].message.content.strip()
                    if "{name}" not in body_text:
                        body_text = f"Hello {{name}},\n\n{body_text}"
                    st.session_state.body = body_text
                    st.success("✅ AI draft ready!")
                except Exception as e:
                    st.error(f"AI error: {e}")

    if "body" not in st.session_state:
        st.session_state.body = "Hello {name},\n\nThis is a personalized email.\n\nBest regards,\nYour Team"

    body = st.text_area("📝 Email Body (use {name} for personalization)", 
                       value=st.session_state.body, height=280, key="body")

    c1, c2, c3 = st.columns(3)
    with c1:
        dry_run = st.checkbox("Dry Run (Preview Only)", value=True)
    with c2:
        delay = st.slider("Delay between emails (sec)", 0, 5, 1)

    if st.button("🚀 Send Emails", type="primary", use_container_width=True):
        if recipients_df is None or "email" not in recipients_df.columns:
            st.error("❌ Email column not found. Please upload file and select column.")
        elif not smtp_user or not smtp_password:
            st.error("❌ SMTP username and password required.")
        elif not subject.strip() or not body.strip():
            st.error("❌ Subject and body are required.")
        else:
            # Filter valid emails
            valid_df = recipients_df[recipients_df["email"].astype(str).str.contains("@", na=False)].copy()
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            sent_count = 0
            failed: List[Tuple[str, str]] = []

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
                        except Exception as send_err:
                            failed.append((recipient, str(send_err)))

                        progress_bar.progress((idx + 1) / len(valid_df))
                        status_text.text(f"Processing {idx+1}/{len(valid_df)} → {recipient}")

                        if delay > 0:
                            time.sleep(delay)

            except Exception as e:
                st.error(f"SMTP Connection Error: {e}")

            st.success(f"✅ Sent: **{sent_count}** / **{len(valid_df)}**")

            if failed:
                st.warning(f"⚠️ Failed: {len(failed)} emails")
                with st.expander("Show Failures"):
                    for email, err in failed[:15]:
                        st.write(f"{email} → {err}")

with col2:
    if recipients_df is not None:
        st.metric("Total Recipients", len(recipients_df))
        st.dataframe(recipients_df.head(6)[["email"] + (["name"] if "name" in recipients_df.columns else [])], 
                    use_container_width=True)

    st.markdown("### 💡 Tips")
    st.markdown("""
    - CSV files are most reliable  
    - Common column names: `email`, `Email`, `email address`  
    - Always test with **Dry Run** first
    """)
