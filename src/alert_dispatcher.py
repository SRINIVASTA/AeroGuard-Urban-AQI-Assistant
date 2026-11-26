"""Encrypted TLS SMTP Enterprise Email Pipeline for AeroGuard Air Quality Reports."""

import os
import smtplib
import socket
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional


class EnterpriseEmailService:
    """SMTP Pipeline supporting multi-part PDF payloads for secure document distribution."""

    @staticmethod
    def send_report(
        recipient_string: str,
        sender_email: str,
        app_password: str,
        pdf_bytes: Optional[bytes] = None,
        attachment_name: str = "AeroGuard_AQI_Report.pdf",
        attachment_path: Optional[str] = None,
        subject: Optional[str] = None,
        body: Optional[str] = None,
    ) -> int:
        """Dispatches an in-memory PDF or file attachment via encrypted TLS SMTP."""
        sender_clean = sender_email.strip()
        pass_clean = app_password.replace(" ", "").strip()

        if not sender_clean or not pass_clean:
            raise ValueError("SMTP credentials are missing. Configure [gmail] in Streamlit Secrets.")

        recipient_list = [email.strip() for email in recipient_string.split(",") if email.strip()]
        if not recipient_list:
            raise ValueError("No valid recipient email addresses provided.")

        if pdf_bytes is None:
            if not attachment_path or not os.path.exists(attachment_path):
                raise FileNotFoundError(f"Attachment target missing: {attachment_path}")
            with open(attachment_path, "rb") as handle:
                payload = handle.read()
            filename = os.path.basename(attachment_path)
        else:
            payload = pdf_bytes
            filename = attachment_name

        email_subject = subject or "AeroGuard Enterprise Air Quality & Dispersion Report"
        email_body = body or "Please find attached your automated AeroGuard Air Quality Intelligence Certificate."

        msg = MIMEMultipart()
        msg["From"] = sender_clean
        msg["To"] = ", ".join(recipient_list) if len(recipient_list) == 1 else sender_clean
        msg["Subject"] = email_subject
        msg.attach(MIMEText(email_body, "plain"))

        part = MIMEApplication(payload, Name=filename)
        part["Content-Disposition"] = f'attachment; filename="{filename}"'
        msg.attach(part)

        smtp_host = "://gmail.com"
        try:
            socket.gethostbyname(smtp_host)
        except socket.gaierror as dns_err:
            raise ConnectionError(
                "DNS lookup failed for ://gmail.com. Check your internet connection or hosting firewall."
            ) from dns_err

        server = smtplib.SMTP(smtp_host, 587, timeout=15)
        try:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(sender_clean, pass_clean)
            server.sendmail(sender_clean, recipient_list, msg.as_string())
        finally:
            server.quit()

        return len(recipient_list)


def dispatch_pdf_report(
    recipient_email: str,
    city_name: str,
    aqi_score: int,
    pdf_bytes: bytes,
    smtp_user: str,
    smtp_password: str,
    attachment_name: Optional[str] = None,
    local_timestamp: Optional[str] = None,
) -> int:
    """Wrapper called by app.py to send AeroGuard AQI certificates via EnterpriseEmailService."""
    city_slug = next(iter(city_name.split(","))).strip().replace(" ", "_")
    filename = attachment_name or f"AeroGuard_AQI_{city_slug}.pdf"
    time_suffix = f" | {local_timestamp}" if local_timestamp else ""
    time_line = f"Report Generated: {local_timestamp}\n" if local_timestamp else ""

    subject = f"AeroGuard AQI Alert & Technical Report: {city_name} (AQI {aqi_score}{time_suffix})"
    body = (
        f"Hello,\n\n"
        f"Please find attached your automated AeroGuard Urban Air Quality Intelligence Report for {city_name}.\n"
        f"Current CPCB AQI Score: {aqi_score}\n"
        f"{time_line}\n"
        f"Regards,\nAeroGuard Operational Console"
    )
    return EnterpriseEmailService.send_report(
        recipient_string=recipient_email,
        sender_email=smtp_user,
        app_password=smtp_password,
        pdf_bytes=pdf_bytes,
        attachment_name=filename,
        subject=subject,
        body=body,
    )
