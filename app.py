import os

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# Generic Error and Technical Error are intentionally not adjacent.
STANDARD_FAILURE_TYPES = [
    "Transaction Limit Breach",
    "Generic Error",
    "System Timeout",
    "Card Blocked or Expired",
    "Technical Error",
    "Insufficient Funds",
]

BILL_PAYMENTS_CC_FAILURE_TYPES = [
    "Transaction Limit Breach",
    "Generic Error",
    "System Timeout",
    "Card Blocked or Expired",
    "Technical Error",
]

AMEX_FAILURE_TYPES = [
    "Transaction Limit Breach",
    "Generic Error",
    "System Timeout",
    "Card Blocked or Expired",
    "Technical Error",
]

BANK_NAMES = [
    "HDFC",
    "ICICI",
    "Axis",
    "Kotak",
    "Yes Bank",
    "SBI",
    "PNB",
    "Bank of Baroda",
    "AU Small Finance",
    "Equitas",
    "Other",
]

BANKING_PAYMENT_MODES = [
    "Funds Transfer",
    "Bill Payments",
    "Debit Card Payment",
    "Credit Card Payment",
]

THIRD_PARTY_PAYMENT_MODES = [
    "Credit Card Payment",
    "Funds Transfer",
    "Bill Payments",
    "Debit Card Payment",
]

CRED_PAYMENT_MODES = [
    "Credit Card Payment",
    "Bill Payments",
]

BANK_HELPLINES = {
    "HDFC": "1800-202-6161",
    "ICICI": "1800-1080",
    "Axis": "1800-419-5959",
    "SBI": "1800-1234",
    "Kotak": "1860-266-2666",
    "PNB": "1800-180-2222",
    "Bank of Baroda": "1800-5700",
    "AU Small Finance": "1800-1200",
    "Equitas": "1800-103-1222",
    "Yes Bank": "1800-1200",
}

AMEX_CONTACT = (
    "For further assistance contact American Express India: "
    "1800-419-2122 (24x7, toll free)"
)

THIRD_PARTY_CONTACTS = {
    "Google Pay": "For further assistance contact Google Pay Support: gpay.app/support",
    "PhonePe": "For further assistance contact PhonePe Support: 080-68727374",
    "Cred": "For further assistance contact CRED Support: cred.club/support",
}

DISCLAIMER = (
    "Disclaimer: This is general guidance only. Please verify with your bank "
    "statement or contact your bank for account-specific queries."
)

SYSTEM_PROMPT = (
    "You are a helpful payment support assistant with expertise in Indian banking. "
    "You receive structured context: usage type (Banking Platforms, Third-Party App, or "
    "Credit Card Network App), issuing bank, platform, card network, payment mode, payment "
    "source, failure type, and a user description.\n\n"
    "FLOW-SPECIFIC GUIDANCE:\n"
    "- Banking Platforms: Factor in Bank Name, Platform (mobile app vs web banking), "
    "Payment Mode (Funds Transfer, Bill Payments, Debit Card Payment, Credit Card Payment), "
    "and Payment Source when Bill Payments is selected (Savings Account vs Credit Card). "
    "Limits, timeouts, and failure patterns differ by these variables.\n"
    "- Credit Card Network App: All responses must be American Express-specific — Amex "
    "acceptance networks, Amex card behaviour, Amex-specific limits, and Amex support paths. "
    "Do not reference Visa, Mastercard, or RuPay. Do NOT include Amex contact details in "
    "your response — they are appended automatically by the system.\n"
    "- Third-Party App: Factor in which third-party platform was selected (Google Pay, "
    "PhonePe, or Cred). Tokenised cards, app-specific limits, and retry flows differ "
    "by platform. Do NOT include third-party app contact details in your response — they "
    "are appended automatically by the system.\n\n"
    "CRITICAL RULES:\n"
    "1. The selected Failure Type is the primary driver of your diagnosis — not the free text alone. "
    "Always diagnose according to the selected failure type first.\n"
    "2. If the user's description clearly does NOT match the selected Failure Type (e.g. they "
    "selected 'System Timeout' but describe a PIN or credential issue), OR if the description "
    "is irrelevant to any banking or payment issue (e.g. a random name or unrelated text), "
    "do NOT generate a fabricated diagnosis. Respond with exactly: "
    "\"The failure type selected and the description you provided don't seem related. "
    "Please double check your selection or rewrite your description so we can help you accurately.\"\n"
    "3. For 'Generic Error' and 'Technical Error': give a warm, reassuring generic response. "
    "Do NOT mention any specific error type, error code, or root cause. Acknowledge the issue, "
    "assure the user that help is available, and direct them to contact the relevant support "
    "channel. Do not attempt to diagnose a specific cause for these two failure types.\n"
    "4. For 'Transaction Limit Breach': do NOT include any 'your money is safe' or 'no money at "
    "risk' reassurance — no transaction was attempted. Go directly into explaining possible "
    "reasons for the limit error and resolution steps.\n"
    "5. For 'Insufficient Funds': do NOT mention transaction limits or daily/monthly limits. "
    "Focus only on balance-related causes (available balance vs ledger balance, holds, pending debits).\n"
    "6. For 'System Timeout': START with money-safety reassurance — the user may not know if "
    "money was debited. Then explain timeout causes and next steps.\n"
    "7. For 'Card Blocked or Expired': focus on card status, expiry, and reissuance — not generic app troubleshooting.\n"
    "8. Banking Platforms only: always include the bank helpline at the end of your response "
    "if it is provided in the context. Format it as: 'For further assistance contact [Bank Name] "
    "customer care: [helpline number]'. If bank is Other, say 'contact your bank customer care'.\n"
    "9. Mobile app and web banking responses must be equally specific and accurate.\n"
    "10. Keep response under 150 words in plain simple English.\n"
    "11. End with: Disclaimer: This is general guidance only. Please verify with your bank "
    "statement or contact your bank for account-specific queries."
)

USAGE_OPTIONS = [
    "Banking Platforms",
    "Third-Party App",
    "Credit Card Network App",
]


def banking_failure_types(payment_mode: str | None, payment_source: str | None) -> list[str]:
    if payment_mode == "Bill Payments" and payment_source == "Credit Card":
        return BILL_PAYMENTS_CC_FAILURE_TYPES
    return STANDARD_FAILURE_TYPES


def third_party_payment_modes(platform: str | None) -> list[str]:
    if platform == "Cred":
        return CRED_PAYMENT_MODES
    return THIRD_PARTY_PAYMENT_MODES


def build_user_message(
    usage_type: str,
    platform: str | None,
    bank_name: str | None,
    card_network: str | None,
    payment_mode: str | None,
    payment_source: str | None,
    failure_type: str,
    description: str,
) -> str:
    fields = [("I am using", usage_type)]
    if bank_name:
        fields.append(("Issuing Bank", bank_name))
        if bank_name in BANK_HELPLINES:
            fields.append(("Bank Helpline", BANK_HELPLINES[bank_name]))
        else:
            fields.append(("Bank Helpline", "contact your bank customer care"))
    if card_network:
        fields.append(("Card Network", card_network))
    if platform:
        fields.append(("Platform", platform))
    if payment_mode:
        fields.append(("Payment Mode", payment_mode))
    if payment_source:
        fields.append(("Payment Source", payment_source))
    fields.extend(
        [
            ("Failure Type", failure_type),
            ("User Description", description.strip()),
        ]
    )
    return "\n".join(f"{label}: {value}" for label, value in fields)


def format_diagnosis_response(
    usage_type: str,
    platform: str | None,
    bank_name: str | None,
    result: str,
) -> str:
    diagnosis = result.strip()

    # Strip disclaimer from AI response — we append it ourselves in correct order
    if "Disclaimer:" in diagnosis:
        diagnosis = diagnosis[: diagnosis.rfind("Disclaimer:")].strip()

    # Also strip any bank contact line from AI output for Banking Platforms
    # (AI includes it inline — we keep it as part of diagnosis text for Banking Platforms)

    contact = None
    if usage_type == "Credit Card Network App":
        contact = AMEX_CONTACT
    elif usage_type == "Third-Party App" and platform:
        contact = THIRD_PARTY_CONTACTS.get(platform)

    # Order: diagnosis → contact details → disclaimer
    parts = [diagnosis]
    if contact:
        parts.append(contact)
    parts.append(DISCLAIMER)
    return "\n\n".join(parts)


def get_diagnosis(user_message: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY not found. Add it to your .env file in the project root."
        )

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=512,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
    )
    return response.choices[0].message.content


def main() -> None:
    st.set_page_config(
        page_title="Payment Triage System",
        page_icon="💳",
        layout="centered",
    )

    st.title("Payment Triage System")

    usage_type = st.selectbox(
        "I am using",
        USAGE_OPTIONS,
        index=None,
        placeholder="Select an option",
    )

    platform = None
    bank_name = None
    card_network = None
    payment_mode = None
    payment_source = None
    failure_type = None

    if usage_type == "Banking Platforms":
        bank_name = st.selectbox(
            "Bank Name",
            BANK_NAMES,
            index=None,
            placeholder="Select bank",
        )
        platform = st.selectbox(
            "Platform",
            ["Mobile App", "Web Banking"],
            index=None,
            placeholder="Select platform",
        )
        payment_mode = st.selectbox(
            "Payment Mode",
            BANKING_PAYMENT_MODES,
            index=None,
            placeholder="Select payment mode",
        )

        if payment_mode == "Bill Payments":
            payment_source = st.selectbox(
                "Payment Source",
                ["Savings Account", "Credit Card"],
                index=None,
                placeholder="Select payment source",
            )

        if payment_mode == "Bill Payments" and not payment_source:
            st.caption("Select a Payment Source to see Failure Type options.")
        else:
            failure_type = st.selectbox(
                "Failure Type",
                banking_failure_types(payment_mode, payment_source),
                index=None,
                placeholder="Select failure type",
            )

    elif usage_type == "Credit Card Network App":
        card_network = st.selectbox(
            "Card Network",
            ["American Express"],
            index=None,
            placeholder="Select card network",
        )
        platform = st.selectbox(
            "Platform",
            ["Mobile App", "Web Banking"],
            index=None,
            placeholder="Select platform",
        )
        failure_type = st.selectbox(
            "Failure Type",
            AMEX_FAILURE_TYPES,
            index=None,
            placeholder="Select failure type",
        )

    elif usage_type == "Third-Party App":
        platform = st.selectbox(
            "Platform",
            ["Google Pay", "PhonePe", "Cred"],
            index=None,
            placeholder="Select platform",
        )
        bank_name = st.selectbox(
            "Bank Name",
            BANK_NAMES,
            index=None,
            placeholder="Select bank",
        )
        payment_mode = st.selectbox(
            "Payment Mode",
            third_party_payment_modes(platform),
            index=None,
            placeholder="Select payment mode",
        )
        failure_type = st.selectbox(
            "Failure Type",
            STANDARD_FAILURE_TYPES,
            index=None,
            placeholder="Select failure type",
        )

    description = st.text_area(
        "Describe what happened",
        placeholder="Briefly describe the error message or what you observed…",
        height=120,
    )

    submitted = st.button("Submit", type="primary", use_container_width=True)

    if submitted:
        if not usage_type:
            st.error("Please select an option under 'I am using'.")
            return

        if failure_type is None:
            st.error("Please select a failure type.")
            return

        if usage_type == "Banking Platforms":
            if not bank_name or not platform or not payment_mode:
                st.error("Please fill in all required fields.")
                return
            if payment_mode == "Bill Payments" and not payment_source:
                st.error("Please select a Payment Source for Bill Payments.")
                return

        if usage_type == "Credit Card Network App":
            if not card_network or not platform:
                st.error("Please fill in all required fields.")
                return

        if usage_type == "Third-Party App":
            if not platform or not bank_name or not payment_mode:
                st.error("Please fill in all required fields.")
                return

        if not description.strip():
            st.error("Please describe what happened.")
            return

        user_message = build_user_message(
            usage_type=usage_type,
            platform=platform,
            bank_name=bank_name,
            card_network=card_network,
            payment_mode=payment_mode,
            payment_source=payment_source,
            failure_type=failure_type,
            description=description,
        )

        with st.spinner("Analyzing your payment issue…"):
            try:
                result = get_diagnosis(user_message)
                result = format_diagnosis_response(usage_type, platform, bank_name, result)
                st.success("Diagnosis")
                st.markdown(result)
            except ValueError as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(f"Unable to get a diagnosis right now. Please try again. ({exc})")


if __name__ == "__main__":
    main()
