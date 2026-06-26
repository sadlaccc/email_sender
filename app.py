import io
import os
import smtplib
from email.message import EmailMessage

import pandas as pd
import streamlit as st

try:
    import openai
    openai_available = True
except ImportError:
    openai_available = False

st.set_page_config(page_title="Bulk Email Sender", page_icon="✉️", layout="centered")
stitle = "Bulk Email Sender"

st.title(stitle)
st.write(
    "Upload a list of recipient emails, compose your message, and send personalized emails in bulk. "
    "The CSV must contain an `email` column and may optionally include a `name` column for template personalization."
)

with st.sidebar:
    st.header("SMTP Settings")
    smtp_server = st.text_input("SMTP Server", value="smtp.gmail.com")
    smtp_port = st.number_input("SMTP Port", value=587, min_value=1, max_value=65535)
    smtp_user = st.text_input("SMTP Username / Email")
    smtp_password = st.text_input("SMTP Password", type="password")
    openai_api_key = st.text_input("OpenAI API Key", type="password")
    st.markdown(
        "---\n"
        "**Note:** For Gmail, use an App Password or allow SMTP access for your account. "
        "Never share credentials publicly."
    )

uploaded_file = st.file_uploader("Upload recipients CSV", type=["csv", "txt"])

st.markdown(
    """
    <style>
    .stApp {background: #f5f7ff;}
    .stButton>button {background: linear-gradient(90deg, #4f46e5 0%, #2563eb 100%); color: white; border: none; border-radius: 0.85rem; height: 3rem; font-weight: 600;}
    .stTextInput>div>div>input, .stTextArea>div>div>textarea, .stNumberInput>div>div>input {border-radius: 0.75rem;}
    .stFileUploader, .stMarkdown, .stExpander {background: white; border-radius: 1rem; padding: 1rem;}
    .stAlert, .stMarkdown p {font-size: 0.95rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

recipients_df = None
if uploaded_file is not None:
    try:
        raw_data = uploaded_file.read()
        try:
            recipients_df = pd.read_csv(io.StringIO(raw_data.decode("utf-8")))
        except UnicodeDecodeError:
            recipients_df = pd.read_csv(io.StringIO(raw_data.decode("latin-1")))
    except Exception as exc:
        st.error(f"Could not read the uploaded file: {exc}")

main_col, sidebar_col = st.columns([3, 1])
with main_col:
    if "body" not in st.session_state:
        st.session_state.body = (
            "Hello {name},\n\nThis is a bulk email sent via Streamlit.\n\nBest regards,\n[Your Name]"
        )

    subject = st.text_input("Email Subject")
    use_ai = st.checkbox("Use AI to design the email copy", value=False)
    if use_ai:
        st.markdown("### AI Email Drafting")
        ai_prompt = st.text_area(
            "AI Prompt",
            value=(
                "Write a friendly, personalized bulk email message for {name} introducing our offering. "
                "Keep it concise and professional with a clear call to action."
            ),
            height=150,
        )
        if not openai_available:
            st.warning("Install the `openai` package to enable AI email generation.")
        else:
            if st.button("Generate AI Email Draft"):
                if not (openai_api_key or os.getenv("OPENAI_API_KEY")):
                    st.error("Enter your OpenAI API key in the sidebar or set OPENAI_API_KEY.")
                elif not subject.strip():
                    st.error("Provide an email subject before generating an AI draft.")
                else:
                    try:
                        openai.api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
                        prompt_text = (
                            "You are a professional email copywriter. "
                            "Use the placeholder {name} for personalization and produce a clean, friendly email body. "
                            f"Subject: {subject}\n"
                            f"Instructions: {ai_prompt}\n"
                            "Output only the email body without the subject."
                        )
                        response = openai.ChatCompletion.create(
                            model="gpt-3.5-turbo",
                            messages=[
                                {"role": "system", "content": "You write professional bulk email copy."},
                                {"role": "user", "content": prompt_text},
                            ],
                            temperature=0.7,
                            max_tokens=400,
                        )
                        generated_body = response.choices[0].message["content"].strip()
                        if "{name}" not in generated_body:
                            generated_body = "Hello {name},\n\n" + generated_body
                        st.session_state.body = generated_body
                        st.success("AI-generated email draft inserted into the body field.")
                    except Exception as ai_error:
                        st.error(f"AI generation failed: {ai_error}")

    body = st.text_area("Email Body", value=st.session_state.body, key="body", height=250)
    submit_pressed = st.button("Submit")

    if submit_pressed:
        if recipients_df is None:
            st.error("Please upload a recipients CSV before submitting.")
        elif "email" not in recipients_df.columns:
            st.error("The uploaded file must contain an `email` column.")
        elif not smtp_user or not smtp_password:
            st.error("Please enter SMTP username and password.")
        elif not subject.strip():
            st.error("Please enter an email subject.")
        elif not body.strip():
            st.error("Please enter an email body.")
        else:
            total = len(recipients_df)
            sent_count = 0
            failed = []

            with st.spinner("Sending emails..."):
                try:
                    with smtplib.SMTP(smtp_server, smtp_port, timeout=30) as smtp:
                        smtp.ehlo()
                        if smtp_port == 587:
                            smtp.starttls()
                            smtp.ehlo()
                        smtp.login(smtp_user, smtp_password)

                        for _, row in recipients_df.iterrows():
                            recipient = str(row.get("email", "")).strip()
                            if not recipient:
                                failed.append((recipient, "Missing email address"))
                                continue

                            recipient_name = str(row.get("name", "")).strip() if "name" in recipients_df.columns else ""
                            personalized_body = body.format(name=recipient_name or "there")

                            message = EmailMessage()
                            message["From"] = smtp_user
                            message["To"] = recipient
                            message["Subject"] = subject
                            message.set_content(personalized_body)

                            try:
                                smtp.send_message(message)
                                sent_count += 1
                            except Exception as exc:
                                failed.append((recipient, str(exc)))

                except Exception as connection_error:
                    st.error(f"SMTP connection failed: {connection_error}")
                    st.stop()

            st.success(f"Emails sent: {sent_count} / {total}")
            if failed:
                st.warning(f"Failed to send {len(failed)} emails.")
                st.write("### Failures")
                for recipient, error in failed:
                    st.write(f"- {recipient or '[missing email]'}: {error}")

with sidebar_col:
    st.markdown("### Quick Tips")
    st.write(
        "- Use `{name}` to personalize the body.\n"
        "- Keep your subject short and action-oriented.\n"
        "- Use AI only when you want a fast draft."
    )
    if recipients_df is not None and "email" in recipients_df.columns:
        st.markdown("### Recipients Preview")
        st.metric("Loaded recipients", len(recipients_df))
        st.dataframe(recipients_df.head(8))

if uploaded_file is None:
    st.info("Upload a CSV file to begin.")
