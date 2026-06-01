"""Wallet Service GraphQL schema — race-condition safe."""

from decimal import Decimal
import graphene
from graphene_django import DjangoObjectType
from django.db import transaction as db_transaction
from django.db.models import F
from django.utils import timezone

from .models import Wallet, WalletTransaction
from ecom_backend.event_bus import publish_event


class WalletType(DjangoObjectType):
    class Meta:
        model = Wallet
        name = 'WalletServiceWalletType'
        fields = ['id', 'balance', 'pending_balance', 'currency', 'created_at', 'updated_at']


class WalletTransactionType(DjangoObjectType):
    class Meta:
        model = WalletTransaction
        name = 'WalletServiceWalletTransactionType'
        fields = ['id', 'type', 'amount', 'status', 'description', 'reference', 'created_at']


class WalletQuery(graphene.ObjectType):
    wallet = graphene.Field(WalletType)
    wallet_transactions = graphene.List(WalletTransactionType)

    def resolve_wallet(self, info):
        user = info.context.user
        if user.is_anonymous:
            raise Exception('Not logged in!')
        wallet, _ = Wallet.objects.get_or_create(customer=user)
        return wallet

    def resolve_wallet_transactions(self, info):
        user = info.context.user
        if user.is_anonymous:
            raise Exception('Not logged in!')
        wallet, _ = Wallet.objects.get_or_create(customer=user)
        return wallet.transactions.all()


class TopUpWalletMutation(graphene.Mutation):
    """
    Initiate a wallet top-up.
    The balance is incremented only after the external payment gateway confirms
    receipt of funds (via the PaymentCompleted webhook).
    This mutation creates a PENDING transaction and publishes WalletTopUpRequested.
    The webhook handler in gateway_schema.py finalises the credit.
    """
    class Arguments:
        amount    = graphene.Decimal(required=True)
        reference = graphene.String(required=False)

    success     = graphene.Boolean()
    message     = graphene.String()
    wallet      = graphene.Field(WalletType)
    transaction = graphene.Field(WalletTransactionType)

    @classmethod
    def mutate(cls, root, info, amount, reference=None):
        user = info.context.user
        if user.is_anonymous:
            raise Exception('Not logged in!')

        amount = Decimal(str(amount))
        if amount <= 0:
            return cls(success=False, message='Amount must be greater than zero')

        with db_transaction.atomic():
            wallet, _ = Wallet.objects.get_or_create(customer=user)

            # Record as PENDING — balance credited only on gateway confirmation
            tx = WalletTransaction.objects.create(
                wallet=wallet,
                type=WalletTransaction.TransactionType.CREDIT,
                amount=amount,
                status=WalletTransaction.TransactionStatus.PENDING,
                description='Wallet top-up (pending gateway confirmation)',
                reference=reference or '',
            )

        publish_event('payment.events', 'WalletTopUpRequested', {
            'user_id':        str(user.id),
            'wallet_id':      str(wallet.id),
            'transaction_id': str(tx.id),
            'amount':         str(amount),
            'reference':      tx.reference,
        })

        return cls(
            success=True,
            message='Top-up initiated — funds will appear after payment confirmation',
            wallet=wallet,
            transaction=tx,
        )


class ConfirmWalletTopUpMutation(graphene.Mutation):
    """
    Internal mutation called by the payment webhook handler to credit the wallet
    after the external gateway confirms receipt.  Not exposed to end-users.
    """
    class Arguments:
        transaction_id = graphene.ID(required=True)

    success = graphene.Boolean()

    @classmethod
    def mutate(cls, root, info, transaction_id):
        try:
            with db_transaction.atomic():
                tx = WalletTransaction.objects.select_for_update().get(
                    pk=int(transaction_id),
                    status=WalletTransaction.TransactionStatus.PENDING,
                    type=WalletTransaction.TransactionType.CREDIT,
                )
                # Atomic increment — prevents double-credit race condition
                Wallet.objects.filter(pk=tx.wallet_id).update(
                    balance=F('balance') + tx.amount,
                    updated_at=timezone.now(),
                )
                tx.status = WalletTransaction.TransactionStatus.COMPLETED
                tx.save(update_fields=['status'])
        except WalletTransaction.DoesNotExist:
            return cls(success=False)
        return cls(success=True)


class WithdrawWalletMutation(graphene.Mutation):
    class Arguments:
        amount    = graphene.Decimal(required=True)
        reference = graphene.String(required=False)

    success     = graphene.Boolean()
    message     = graphene.String()
    wallet      = graphene.Field(WalletType)
    transaction = graphene.Field(WalletTransactionType)

    @classmethod
    def mutate(cls, root, info, amount, reference=None):
        user = info.context.user
        if user.is_anonymous:
            raise Exception('Not logged in!')

        amount = Decimal(str(amount))
        if amount <= 0:
            return cls(success=False, message='Amount must be greater than zero')

        with db_transaction.atomic():
            # select_for_update prevents concurrent over-withdrawal
            wallet = Wallet.objects.select_for_update().get_or_create(customer=user)[0]
            if wallet.balance < amount:
                return cls(success=False, message='Insufficient wallet balance')

            Wallet.objects.filter(pk=wallet.pk).update(
                balance=F('balance') - amount,
                updated_at=timezone.now(),
            )
            wallet.refresh_from_db()

            tx = WalletTransaction.objects.create(
                wallet=wallet,
                type=WalletTransaction.TransactionType.DEBIT,
                amount=amount,
                status=WalletTransaction.TransactionStatus.COMPLETED,
                description='Wallet withdrawal',
                reference=reference or '',
            )

        publish_event('payment.events', 'WalletWithdrawalRequested', {
            'user_id':        str(user.id),
            'wallet_id':      str(wallet.id),
            'transaction_id': str(tx.id),
            'amount':         str(amount),
            'reference':      tx.reference,
        })

        return cls(
            success=True,
            message='Withdrawal successful',
            wallet=wallet,
            transaction=tx,
        )


class WalletMutation(graphene.ObjectType):
    top_up_wallet          = TopUpWalletMutation.Field()
    confirm_wallet_top_up  = ConfirmWalletTopUpMutation.Field()
    withdraw_wallet        = WithdrawWalletMutation.Field()
