"""Emails the .xlsx report as an attachment via Gmail SMTP, using an app
password (never the real account password) stored as GitHub secrets - see
README.md "GitHub setup, step by step"."""
import os
import smtplib
from email.message import EmailMessage
from pathlib import Path


def send_report_email(xlsx_path, comparison: list[dict], run_ts: str) -> None:
    sender = os.environ["REPORT_EMAIL_FROM"]
    password = os.environ["REPORT_EMAIL_APP_PASSWORD"]
    recipient = os.environ["REPORT_EMAIL_TO"]

    movers = sorted(
        (r for r in comparison if r.get("pct_vs_prev")),
        key=lambda r: abs(r["pct_vs_prev"]),
        reverse=True,
    )[:8]

    lines = [f"Glasgow student accommodation comp set - {run_ts}", ""]
    if movers:
        lines.append("Biggest moves since the last report:")
        for r in movers:
            lines.append(
                f"  {r['property_name']} - {r['room_type']}: "
                f"£{r['price_pw']:.2f} ({r['pct_vs_prev']:+.1f}%)"
            )
    else:
        lines.append("No price changes since the last report.")
    lines += ["", "Full side-by-side comparison attached."]

    msg = EmailMessage()
    msg["Subject"] = f"Glasgow comp set report - {run_ts[:16].replace('T', ' ')}"
    msg["From"] = sender
    msg["To"] = recipient
    msg.set_content("\n".join(lines))

    xlsx_path = Path(xlsx_path)
    with open(xlsx_path, "rb") as f:
        msg.add_attachment(
            f.read(),
            maintype="application",
            subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=xlsx_path.name,
        )

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(sender, password)
        smtp.send_message(msg)
