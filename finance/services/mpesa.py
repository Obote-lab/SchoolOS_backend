import logging
from decimal import Decimal

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from core.choices.finance import PaymentMethodChoices, PaymentStatusChoices
from finance.models import Payment
from finance.services.mpesa_utils import (
    generate_password,
    generate_timestamp,
    normalize_phone,
)

logger = logging.getLogger(__name__)


class MpesaError(Exception):
    """Custom exception for M-Pesa related errors"""
    pass


class MpesaService:
    """
    Safaricom Daraja API client + business logic for SchoolOS.
    """

    def __init__(self):
        self.environment = getattr(settings, "MPESA_ENVIRONMENT", "sandbox")
        self.consumer_key = settings.MPESA_CONSUMER_KEY
        self.consumer_secret = settings.MPESA_CONSUMER_SECRET
        self.shortcode = settings.MPESA_SHORTCODE
        self.passkey = settings.MPESA_PASSKEY
        self.callback_url = settings.MPESA_CALLBACK_URL
        self.transaction_type = getattr(
            settings, "MPESA_TRANSACTION_TYPE", "CustomerPayBillOnline"
        )

        if self.environment == "production":
            self.base_url = "https://api.safaricom.co.ke"
        else:
            self.base_url = "https://sandbox.safaricom.co.ke"

    # Auth
    def get_access_token(self) -> str:
        url = f"{self.base_url}/oauth/v1/generate?grant_type=client_credentials"
        try:
            response = requests.get(
                url,
                auth=(self.consumer_key, self.consumer_secret),
                timeout=30,
            )
            response.raise_for_status()
            return response.json()["access_token"]
        except Exception as e:
            logger.exception("Failed to get M-Pesa access token")
            raise MpesaError(f"Could not obtain access token: {e}") from e

    # STK Push
    def stk_push(
        self,
        *,
        phone: str,
        amount: Decimal,
        account_reference: str,
        transaction_desc: str,
        invoice=None,
        student=None,
        school=None,
        initiated_by=None,
    ) -> Payment:
        """
        Initiate Lipa Na M-Pesa Online (STK Push).

        Returns the created Payment record (status=PENDING).
        """
        phone = normalize_phone(phone)
        amount = Decimal(amount).quantize(Decimal("1"))  # M-Pesa expects whole shillings

        if amount < 1:
            raise MpesaError("Amount must be at least KES 1")

        timestamp = generate_timestamp()
        password = generate_password(self.shortcode, self.passkey, timestamp)
        token = self.get_access_token()

        payload = {
            "BusinessShortCode": self.shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": self.transaction_type,
            "Amount": int(amount),
            "PartyA": phone,
            "PartyB": self.shortcode,
            "PhoneNumber": phone,
            "CallBackURL": self.callback_url,
            "AccountReference": account_reference[:12],  # max 12 chars
            "TransactionDesc": transaction_desc[:13],    # max 13 chars
        }

        url = f"{self.base_url}/mpesa/stkpush/v1/processrequest"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            data = response.json()
        except Exception as e:
            logger.exception("STK Push request failed")
            raise MpesaError(f"STK Push request failed: {e}") from e

        # Safaricom returns ResponseCode "0" on success
        if str(data.get("ResponseCode")) != "0":
            error_msg = data.get("ResponseDescription") or data.get("errorMessage") or str(data)
            logger.error("STK Push rejected by Safaricom: %s", data)
            raise MpesaError(error_msg)

        checkout_request_id = data.get("CheckoutRequestID", "")
        merchant_request_id = data.get("MerchantRequestID", "")

        # Create PENDING payment record
        with transaction.atomic():
            payment = Payment.objects.create(
                invoice=invoice,
                student=student or (invoice.student if invoice else None),
                school=school or (invoice.school if invoice else None),
                amount=amount,
                method=PaymentMethodChoices.MPESA,
                payment_status=PaymentStatusChoices.PENDING,
                mpesa_transaction_type=Payment.MpesaTransactionType.STK_PUSH,
                checkout_request_id=checkout_request_id,
                merchant_request_id=merchant_request_id,
                mpesa_phone=phone,
                received_by=initiated_by,
                paid_at=timezone.now(),
            )

        logger.info(
            "STK Push initiated | Payment=%s | CheckoutRequestID=%s | Phone=%s | Amount=%s",
            payment.payment_reference,
            checkout_request_id,
            phone,
            amount,
        )
        return payment


    # Callback handler (idempotent)
    def handle_stk_callback(self, payload: dict) -> dict:
        """
        Process the STK callback from Safaricom.

        Expected structure (simplified):
        {
            "Body": {
                "stkCallback": {
                "MerchantRequestID": "...",
                "CheckoutRequestID": "...",
                "ResultCode": 0,
                "ResultDesc": "The service request is processed successfully.",
                "CallbackMetadata": {
                    "Item": [
                    {"Name": "Amount", "Value": 1.00},
                    {"Name": "MpesaReceiptNumber", "Value": "xxxxx"},
                    {"Name": "TransactionDate", "Value": 20261014214500},
                    {"Name": "PhoneNumber", "Value": 2547xxxxxxx}
                    ]
                }
                }
            }
        }
        """
        try:
            body = payload.get("Body", {})
            stk_callback = body.get("stkCallback", {})

            checkout_request_id = stk_callback.get("CheckoutRequestID")
            result_code = stk_callback.get("ResultCode")
            result_desc = stk_callback.get("ResultDesc", "")

            if not checkout_request_id:
                logger.warning("Callback missing CheckoutRequestID: %s", payload)
                return {"ResultCode": 1, "ResultDesc": "Missing CheckoutRequestID"}

            with transaction.atomic():
                payment = (
                    Payment.objects.select_for_update()
                    .filter(checkout_request_id=checkout_request_id)
                    .first()
                )

                if not payment:
                    logger.error(
                        "No Payment found for CheckoutRequestID=%s", checkout_request_id
                    )
                    return {"ResultCode": 0, "ResultDesc": "Accepted (no matching payment)"}

                # Already processed?
                if payment.payment_status == PaymentStatusChoices.COMPLETED:
                    logger.info(
                        "Callback already processed for %s", payment.payment_reference
                    )
                    return {"ResultCode": 0, "ResultDesc": "Already processed"}

                # Store raw payload for audit
                payment.mpesa_callback_raw = payload
                payment.mpesa_result_code = str(result_code)
                payment.mpesa_result_desc = result_desc

                if str(result_code) == "0":
                    # Success – extract metadata
                    metadata = {}
                    items = (
                        stk_callback.get("CallbackMetadata", {}).get("Item", []) or []
                    )
                    for item in items:
                        name = item.get("Name")
                        value = item.get("Value")
                        if name:
                            metadata[name] = value

                    payment.mpesa_receipt = str(metadata.get("MpesaReceiptNumber", ""))
                    payment.mpesa_phone = str(metadata.get("PhoneNumber", payment.mpesa_phone))
                    payment.payment_status = PaymentStatusChoices.COMPLETED
                    # amount should already match, but we can double-check if needed

                    payment.save(
                        update_fields=[
                            "mpesa_callback_raw",
                            "mpesa_result_code",
                            "mpesa_result_desc",
                            "mpesa_receipt",
                            "mpesa_phone",
                            "payment_status",
                            "updated_at",
                        ]
                    )
                    # Signals will now:
                    # 1. Create PaymentAllocation
                    # 2. Update invoice balance
                    # 3. Post to General Ledger

                    logger.info(
                        "Payment COMPLETED via STK | %s | Receipt=%s",
                        payment.payment_reference,
                        payment.mpesa_receipt,
                    )
                else:
                    # Failed / cancelled by user
                    payment.payment_status = PaymentStatusChoices.FAILED
                    payment.save(
                        update_fields=[
                            "mpesa_callback_raw",
                            "mpesa_result_code",
                            "mpesa_result_desc",
                            "payment_status",
                            "updated_at",
                        ]
                    )
                    logger.info(
                        "STK failed/cancelled | %s | Code=%s | %s",
                        payment.payment_reference,
                        result_code,
                        result_desc,
                    )

            return {"ResultCode": 0, "ResultDesc": "Success"}

        except Exception as e:
            logger.exception("Error processing STK callback")
            # Still return 0 so Safaricom does not keep retrying
            return {"ResultCode": 0, "ResultDesc": f"Accepted with error: {e}"}