import logging
from decimal import Decimal

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from core.choices.finance import (
    PaymentAccountTypeChoices,
    PaymentMethodChoices,
    PaymentStatusChoices,
)
from finance.models import Payment, SchoolPaymentAccount
from finance.services.mpesa_utils import (
    generate_password,
    generate_timestamp,
    normalize_phone,
)

logger = logging.getLogger(__name__)


class MpesaError(Exception):
    """Custom exception for M-Pesa related errors."""

    pass


class MpesaService:
    """
    Safaricom Daraja API client + business logic for SchoolOS.

    Uses the school's own Paybill/Till (SchoolPaymentAccount) when available.
    Falls back to platform / sandbox credentials otherwise.
    """

    def __init__(self, payment_account=None, school=None):
        self.environment = getattr(settings, "MPESA_ENVIRONMENT", "sandbox")
        self.consumer_key = settings.MPESA_CONSUMER_KEY
        self.consumer_secret = settings.MPESA_CONSUMER_SECRET
        self.callback_url = settings.MPESA_CALLBACK_URL

        self.payment_account = payment_account
        if not self.payment_account and school:
            self.payment_account = SchoolPaymentAccount.get_default_for_school(
                school,
                account_types=[
                    PaymentAccountTypeChoices.PAYBILL,
                    PaymentAccountTypeChoices.TILL,
                ],
            )

        self._apply_account_credentials()

        if self.environment == "production":
            self.base_url = "https://api.safaricom.co.ke"
        else:
            self.base_url = "https://sandbox.safaricom.co.ke"

    def _apply_account_credentials(self):
        """Set shortcode / passkey / transaction_type from account or settings."""
        if self.payment_account and self.payment_account.shortcode:
            self.shortcode = self.payment_account.shortcode
            self.passkey = self.payment_account.passkey or settings.MPESA_PASSKEY
            self.transaction_type = (
                self.payment_account.transaction_type
                or "CustomerPayBillOnline"
            )
        else:
            self.shortcode = settings.MPESA_SHORTCODE
            self.passkey = settings.MPESA_PASSKEY
            self.transaction_type = getattr(
                settings, "MPESA_TRANSACTION_TYPE", "CustomerPayBillOnline"
            )

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

        Uses the school's default Paybill/Till when available.
        Returns the created Payment record (status=PENDING).
        """
        phone = normalize_phone(phone)
        amount = Decimal(amount).quantize(Decimal("1"))  # whole shillings

        if amount < 1:
            raise MpesaError("Amount must be at least KES 1")

        # Resolve school payment account if we still don't have one
        resolved_school = school or (invoice.school if invoice else None)
        if not self.payment_account and resolved_school:
            self.payment_account = SchoolPaymentAccount.get_default_for_school(
                resolved_school,
                account_types=[
                    PaymentAccountTypeChoices.PAYBILL,
                    PaymentAccountTypeChoices.TILL,
                ],
            )
            self._apply_account_credentials()

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
            "AccountReference": account_reference[:12],
            "TransactionDesc": transaction_desc[:13],
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

        if str(data.get("ResponseCode")) != "0":
            error_msg = (
                data.get("ResponseDescription")
                or data.get("errorMessage")
                or str(data)
            )
            logger.error("STK Push rejected by Safaricom: %s", data)
            raise MpesaError(error_msg)

        checkout_request_id = data.get("CheckoutRequestID", "")
        merchant_request_id = data.get("MerchantRequestID", "")

        resolved_student = student or (invoice.student if invoice else None)

        with transaction.atomic():
            payment = Payment.objects.create(
                invoice=invoice,
                student=resolved_student,
                school=resolved_school,
                payment_account=self.payment_account,  # link to school account
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
            "STK Push initiated | Payment=%s | Shortcode=%s | Checkout=%s | Phone=%s | Amount=%s",
            payment.payment_reference,
            self.shortcode,
            checkout_request_id,
            phone,
            amount,
        )
        return payment

    # Callback handler (idempotent)
    def handle_stk_callback(self, payload: dict) -> dict:
        """
        Process the STK callback from Safaricom.
        Idempotent – safe to receive the same callback more than once.
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
                        "No Payment found for CheckoutRequestID=%s",
                        checkout_request_id,
                    )
                    return {
                        "ResultCode": 0,
                        "ResultDesc": "Accepted (no matching payment)",
                    }

                # Already processed?
                if payment.payment_status == PaymentStatusChoices.COMPLETED:
                    logger.info(
                        "Callback already processed for %s",
                        payment.payment_reference,
                    )
                    return {"ResultCode": 0, "ResultDesc": "Already processed"}

                payment.mpesa_callback_raw = payload
                payment.mpesa_result_code = str(result_code)
                payment.mpesa_result_desc = result_desc

                if str(result_code) == "0":
                    metadata = {}
                    items = (
                        stk_callback.get("CallbackMetadata", {}).get("Item", [])
                        or []
                    )
                    for item in items:
                        name = item.get("Name")
                        value = item.get("Value")
                        if name:
                            metadata[name] = value

                    payment.mpesa_receipt = str(
                        metadata.get("MpesaReceiptNumber", "")
                    )
                    payment.mpesa_phone = str(
                        metadata.get("PhoneNumber", payment.mpesa_phone)
                    )
                    payment.payment_status = PaymentStatusChoices.COMPLETED

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
                    # Signals will:
                    # 1. Create PaymentAllocation
                    # 2. Update invoice balance
                    # 3. Post to General Ledger

                    logger.info(
                        "Payment COMPLETED via STK | %s | Receipt=%s | Account=%s",
                        payment.payment_reference,
                        payment.mpesa_receipt,
                        getattr(payment.payment_account, "shortcode", None),
                    )
                else:
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
            # Always return 0 so Safaricom stops retrying
            return {"ResultCode": 0, "ResultDesc": f"Accepted with error: {e}"}