import io
import time
import socket
import smtplib
from email.message import EmailMessage
from typing import Optional, List, Tuple

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Bulk Email Sender", page_icon="✉️", layout="wide")

# ====================== TITLE & DESCRIPTION ======================
st.title("✉️ Bulk Email Sender")
st.markdown("**Professional Bulk Email Tool** — Send personalized emails with any SMTP provider")

# ====================== SIDEBAR ======================
with st.sidebar:
    st.header("🔧 SMTP Settings")
    
    col_server1, col_server2 = st.columns([3, 2])
    with col_server1:
        smtp_server = st.text_input("SMTP Server", value="smtp.intellinksea.com", key="smtp_server")
    with col_server2:
        smtp_port = st.number_input("Port", value=587, min_value=1, max_value=65535, key="smtp_port")
    
    smtp_user = st.text_input("Email Address", placeholder="you@intellinksea.com", key="smtp_user")
    smtp_password = st.text_input("Password", type="password", key="smtp_password")

    st.markdown("---")
    st.info(f"**Current Server:** `{smtp_server}`")

# ====================== TABS FOR BETTER UX ======================
tab1, tab2, tab3 = st.tabs(["📤 Recipients", "✉️ Compose Email", "🚀 Send"])

recipients_df: Optional[pd.DataFrame] = None
email_col_confirmed = False

# ====================== TAB 1: RECIPIENTS ======================
with tab1:
    st.subheader("Upload Recipient List")
    uploaded_file = st.file_uploader(
        "Upload CSV or Excel file", 
        type=["csv", "txt", "xlsx", "xls"], 
        key="file_upload"
    )

    if uploaded_file:
        try:
            if uploaded_file.name.lower().endswith(('.csv', '.txt')):
                recipients_df = pd.read_csv(uploaded_file)
            else:
                recipients_df = pd.read_excel(uploaded_file)

            # Normalize columns
            recipients_df.columns = [str(col).strip().lower() for col in recipients_df.columns]

            st.success(f"✅ Loaded **{len(recipients_df)}** records")

            # Email Column Selection
            st.subheader("Email Column")
            possible_email_cols = [col for col in recipients_df.columns if any(x in col for x in ["email", "mail", "to", "recipient"])]
            
            if possible_email_cols:
                selected_email_col = st.selectbox("Select Email Column", possible_email_cols, index=0)
            else:
                selected_email_col = st.selectbox("Select Email Column", recipients_df.columns)

            if st.button("✅ Confirm Email Column", type="primary"):
                recipients_df = recipients_df.rename(columns={selected_email_col: "email"})
                st.success(f"✅ Using **{selected_email_col}** as email column")
                email_col_confirmed = True
                st.rerun()

            # Preview
            if "email" in recipients_df.columns:
                st.subheader("Preview")
                st.dataframe(recipients_df.head(10), use_container_width=True)
                st.metric("Valid Emails", len(recipients_df[recipients_df["email"].astype(str).str.contains("@", na=False)]))

        except Exception as e:
            st.error(f"Error reading file: {e}")

# ====================== TAB 2: COMPOSE ======================
with tab2:
    st.subheader("Compose Email")

    subject = st.text_input("Subject", placeholder="Important Update From Intellinksea", key="subject")

    col_a, col_b = st.columns([1, 3])
    with col_a:
        html_mode = st.checkbox("Send as HTML", value=False)
    with col_b:
        use_ai = st.checkbox("Use AI to help write", value=False)

    if "body" not in st.session_state:
        st.session_state.body = "Hello {name},\n\nThis is a personalized email.\n\nBest regards,\nYour Team"

    body = st.text_area(
        "Email Body — Use {name} for personalization", 
        value=st.session_state.body, 
        height=300, 
        key="body"
    )

    st.info("Tip: You can use {name} anywhere in the body for personalization.")

# ====================== TAB 3: SEND ======================
with tab3:
    st.subheader("Send Campaign")

    if st.button("🚀 Start Sending Campaign", type="primary", use_container_width=True):
        user = st.session_state.get("smtp_user", "").strip()
        password = st.session_state.get("smtp_password", "").strip()
        server = st.session_state.get("smtp_server", "").strip()

        if not user or not password:
            st.error("❌ Please fill Email Address and Password in the sidebar.")
        elif recipients_df is None or "email" not in recipients_df.columns:
            st.error("❌ Please upload recipients and confirm email column in Tab 1.")
        elif not subject.strip() or not body.strip():
            st.error("❌ Subject and Body are required.")
        else:
            # DNS Check
            try:
                socket.gethostbyname(server)
            except Exception:
                st.error(f"❌ Cannot resolve SMTP server: **{server}**")
                st.info("Try `mail.intellinksea.com` or contact your IT team.")
                st.stop()

            valid_df = recipients_df[recipients_df["email"].astype(str).str.contains("@", na=False)].copy().reset_index(drop=True)

            if len(valid_df) == 0:
                st.error("No valid email addresses found.")
                st.stop()

            progress_bar = st.progress(0)
            status_text = st.empty()
            
            sent_count = 0
            failed: List[Tuple[str, str]] = []

            try:
                with smtplib.SMTP(server, smtp_port, timeout=30) as smtp:
                    smtp.ehlo()
                    if smtp_port in (587, 25):
                        smtp.starttls()
                        smtp.ehlo()
                    smtp.login(user, password)

                    for idx, row in valid_df.iterrows():
                        recipient = str(row["email"]).strip()
                        name = str(row.get("name", "")).strip() or "there"

                        personalized_body = body.replace("{name}", name)

                        msg = EmailMessage()
                        msg["From"] = user
                        msg["To"] = recipient
                        msg["Subject"] = subject
                        
                        if html_mode:
                            msg.add_alternative(personalized_body, subtype="html")
                        else:
                            msg.set_content(personalized_body)

                        try:
                            smtp.send_message(msg)
                            sent_count += 1
                        except Exception as e:
                            failed.append((recipient, str(e)))

                        progress = (idx + 1) / len(valid_df)
                        progress_bar.progress(progress)
                        status_text.text(f"Sending {idx+1}/{len(valid_df)} → {recipient}")

                        time.sleep(1)  # Gentle delay

            except Exception as e:
                st.error(f"SMTP Error: {e}")

            # Final Result
            st.success(f"🎉 Campaign Completed! Sent: **{sent_count}** / **{len(valid_df)}**")

            if failed:
                st.warning(f"⚠️ Failed: {len(failed)} emails")
                with st.expander("View Failed Emails"):
                    for email, error in failed:
                        st.write(f"**{email}** → {error}")

# ====================== FOOTER ======================
st.markdown("---")
st.caption("Bulk Email Sender • Designed for reliability and ease of use")
