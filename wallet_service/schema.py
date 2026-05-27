"""Wallet Service GraphQL schema."""

from decimal import Decimal
import graphene
from graphene_django import DjangoObjectType
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
    class Arguments:
        amount = graphene.Decimal(required=True)
        reference = graphene.String(required=False)

    success = graphene.Boolean()
    message = graphene.String()
    wallet = graphene.Field(WalletType)
    transaction = graphene.Field(WalletTransactionType)

    @classmethod
    def mutate(cls, root, info, amount, reference=None):
        user = info.context.user
        if user.is_anonymous:
            raise Exception('Not logged in!')

        amount = Decimal(str(amount))
        if amount <= 0:
            return TopUpWalletMutation(success=False, message='Amount must be greater than zero')

        wallet, _ = Wallet.objects.get_or_create(customer=user)
        wallet.balance = wallet.balance + amount
        wallet.save(update_fields=['balance', 'updated_at'])

        tx = WalletTransaction.objects.create(
            wallet=wallet,
            type=WalletTransaction.TransactionType.CREDIT,
            amount=amount,
            status=WalletTransaction.TransactionStatus.COMPLETED,
            description='Wallet top-up',
            reference=reference or '',
        )

        publish_event('payment.events', 'WalletTopUpRequested', {
            'user_id': str(user.id),
            'wallet_id': str(wallet.id),
            'transaction_id': str(tx.id),
            'amount': str(amount),
            'reference': tx.reference,
        })

        return TopUpWalletMutation(success=True, message='Wallet topped up', wallet=wallet, transaction=tx)


class WithdrawWalletMutation(graphene.Mutation):
    class Arguments:
        amount = graphene.Decimal(required=True)
        reference = graphene.String(required=False)

    success = graphene.Boolean()
    message = graphene.String()
    wallet = graphene.Field(WalletType)
    transaction = graphene.Field(WalletTransactionType)

    @classmethod
    def mutate(cls, root, info, amount, reference=None):
        user = info.context.user
        if user.is_anonymous:
            raise Exception('Not logged in!')

        amount = Decimal(str(amount))
        if amount <= 0:
            return WithdrawWalletMutation(success=False, message='Amount must be greater than zero')

        wallet, _ = Wallet.objects.get_or_create(customer=user)
        if wallet.balance < amount:
            return WithdrawWalletMutation(success=False, message='Insufficient wallet balance')

        wallet.balance = wallet.balance - amount
        wallet.save(update_fields=['balance', 'updated_at'])

        tx = WalletTransaction.objects.create(
            wallet=wallet,
            type=WalletTransaction.TransactionType.DEBIT,
            amount=amount,
            status=WalletTransaction.TransactionStatus.COMPLETED,
            description='Wallet withdrawal',
            reference=reference or '',
        )

        publish_event('payment.events', 'WalletWithdrawalRequested', {
            'user_id': str(user.id),
            'wallet_id': str(wallet.id),
            'transaction_id': str(tx.id),
            'amount': str(amount),
            'reference': tx.reference,
        })

        return WithdrawWalletMutation(success=True, message='Wallet withdrawal successful', wallet=wallet, transaction=tx)


class WalletMutation(graphene.ObjectType):
    top_up_wallet = TopUpWalletMutation.Field()
    withdraw_wallet = WithdrawWalletMutation.Field()
