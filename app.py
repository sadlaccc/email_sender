import io
import time
import re
import os
from email.message import EmailMessage
from typing import List, Tuple, Optional

import pandas as pd
import streamlit as st

# OpenAI handling
try:
    from openai import OpenAI
    openai_available = True
except ImportError:
    openai_available = False

st.set_page_config(
    page_title="Bulk Email Sender",
    page_icon="✉️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("✉️ Bulk Email Sender")
st.markdown("Upload your recipient list, compose your message, and send personalized bulk emails.")

# ------------------- Sidebar -------------------
with st.sidebar:
    st.header("SMTP Configuration")
    smtp_server = st.text_input("SMTP Server", value="smtp.gmail.com")
    smtp_port = st.number_input("SMTP Port", value=587, min_value=1, max_value=65535)
    smtp_user = st.text_input("SMTP Username / Email")
    smtp_password = st.text_input("SMTP Password / App Password", type="password")

    st.markdown("---")
    st.header("AI Assistance")
    openai_api_key = st.text_input("OpenAI API Key", type="password", help="Optional - for AI email drafting")
    
    st.markdown("---")
    st.info(
        "🔒 **Security Note**\n\n"
        "• Use Gmail App Passwords\n"
        "• Never share this app publicly\n"
        "• Respect sending limits"
    )

# ------------------- File Upload -------------------
uploaded_file = st.file_uploader(
    "Upload recipients (CSV preferred)", 
    type=["csv", "txt", "xls", "xlsx"],
    help="CSV is most reliable. Excel files require 'openpyxl' package."
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
            
        elif file_ext in ["xls", "xlsx"]:
            try:
                recipients_df = pd.read_excel(io.BytesIO(raw_data))
            except ImportError as e:
                if "openpyxl" in str(e).lower():
                    st.error("❌ **openpyxl is required for Excel files**")
                    st.info("Run this command in your terminal:\n\n`pip install openpyxl`")
                    st.stop()
                else:
                    raise
            except Exception as e:
                st.error(f"Failed to read Excel file: {e}")
                st.stop()
        else:
            st.error("Unsupported file type.")
            st.stop()

        # Normalize columns
        recipients_df.columns = [col.strip().lower() for col in recipients_df.columns]

        if "email" not in recipients_df.columns:
            st.error("❌ The file must contain an **email** column.")
            recipients_df = None
        else:
            st.success(f"✅ Loaded **{len(recipients_df)}** recipients successfully")

    except Exception as e:
        st.error(f"Failed to read file: {e}")

# ------------------- Main Content -------------------
col1, col2 = st.columns([3, 1])

with col1:
    subject = st.text_input("📧 Email Subject", placeholder="Special Offer Just for You!")

    use_ai = st.checkbox("✨ Use AI to generate email body", value=False)

    if use_ai and openai_available:
        st.markdown("### AI Email Generator")
        ai_prompt = st.text_area(
            "AI Instructions",
            value="Write a warm, professional, and concise email introducing our product/service with a clear call-to-action.",
            height=120
        )

        if st.button("Generate Draft with AI", type="primary"):
            if not (openai_api_key or os.getenv("OPENAI_API_KEY")):
                st.error("Please provide an OpenAI API key.")
            elif not subject.strip():
                st.error("Please enter a subject first.")
            else:
                try:
                    client = OpenAI(api_key=openai_api_key or os.getenv("OPENAI_API_KEY"))
                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": "You are an expert email copywriter."},
                            {"role": "user", "content": f"""Subject: {subject}
Instructions: {ai_prompt}

Generate only the email body. Use {{name}} for personalization."""}
                        ],
                        temperature=0.7,
                        max_tokens=500
                    )
                    generated_body = response.choices[0].message.content.strip()
                    if "{name}" not in generated_body:
                        generated_body = f"Hello {{name}},\n\n{generated_body}"
                    
                    st.session_state.body = generated_body
                    st.success("✅ AI draft generated!")
                except Exception as e:
                    st.error(f"AI generation failed: {e}")

    # Email Body
    if "body" not in st.session_state:
        st.session_state.body = "Hello {name},\n\nThis is a test bulk email.\n\nBest regards,\nYour Name"

    body = st.text_area(
        "📝 Email Body (use {name} for personalization)",
        value=st.session_state.body,
        height=300,
        key="body"
    )

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        dry_run = st.checkbox("Dry Run (preview only)", value=True)
    with col_b:
        delay = st.slider("Delay between emails (seconds)", 0, 5, 1)
    with col_c:
        html_mode = st.checkbox("Send as HTML", value=False)

    # Send Button
    if st.button("🚀 Send Emails", type="primary", use_container_width=True):
        if recipients_df is None:
            st.error("Please upload a recipient file.")
        elif "email" not in recipients_df.columns:
            st.error("File must have an 'email' column.")
        elif not smtp_user or not smtp_password:
            st.error("SMTP credentials are required.")
        elif not subject.strip():
            st.error("Subject is required.")
        elif not body.strip():
            st.error("Email body is required.")
        else:
            # Basic email validation
            valid_mask = recipients_df["email"].astype(str).str.strip().str.match(r"[^@]+@[^@]+\.[^@]+")
            valid_df = recipients_df[valid_mask].copy().reset_index(drop=True)
            
            st.info(f"Preparing to send to **{len(valid_df)}** valid emails...")

            progress_bar = st.progress(0)
            status_text = st.empty()
            
            sent_count = 0
            failed: List[Tuple[str, str]] = []

            try:
                with smtplib.SMTP(smtp_server, smtp_port, timeout=30) as smtp:
                    smtp.ehlo()
                    if smtp_port in (587, 25):
                        smtp.starttls()
                        smtp.ehlo()
                    smtp.login(smtp_user, smtp_password)

                    for idx, row in valid_df.iterrows():
                        recipient = str(row["email"]).strip()
                        name = str(row.get("name", "")).strip() or "there"

                        personalized_body = body.replace("{name}", name)

                        msg = EmailMessage()
                        msg["From"] = smtp_user
                        msg["To"] = recipient
                        msg["Subject"] = subject
                        
                        if html_mode and "<html" in personalized_body.lower():
                            msg.add_alternative(personalized_body, subtype="html")
                        else:
                            msg.set_content(personalized_body)

                        try:
                            if not dry_run:
                                smtp.send_message(msg)
                            sent_count += 1
                        except Exception as e:
                            failed.append((recipient, str(e)))

                        progress_bar.progress((idx + 1) / len(valid_df))
                        status_text.text(f"Sending {idx+1}/{len(valid_df)} → {recipient}")

                        if delay > 0:
                            time.sleep(delay)

            except Exception as e:
                st.error(f"SMTP Connection Error: {e}")

            st.success(f"✅ Successfully sent: **{sent_count}** / **{len(recipients_df)}**")

            if failed:
                st.warning(f"⚠️ Failed to send {len(failed)} emails")
                with st.expander("View Failed Emails"):
                    for email, error in failed[:20]:  # limit display
                        st.write(f"**{email}**: {error}")
                    if len(failed) > 20:
                        st.write(f"... and {len(failed)-20} more.")

with col2:
    if recipients_df is not None:
        st.metric("Total Recipients", len(recipients_df))
        st.dataframe(recipients_df.head(6), use_container_width=True)

    st.markdown("### 💡 Tips")
    st.markdown("""
    - **CSV is recommended** (most reliable)
    - For Excel: run `pip install openpyxl`
    - Use `{name}` for personalization
    - Enable **Dry Run** first
    - Add delay to avoid rate limits
    """)

if not uploaded_file:
    st.info("👆 Upload your recipient list (CSV or Excel) to begin.")
