"""
Card Vault GraphQL Schema
=========================
Provides PCI DSS compliant card tokenization.

Flow:
  1. Client fetches RSA public key  →  paymentPublicKey query
  2. Client encrypts card JSON with RSA-OAEP in the browser (SubtleCrypto)
  3. Client calls tokenizeCard(encryptedPayload)
  4. Server decrypts, validates (Luhn + expiry + CVV format), tokenizes
  5. AES-256-GCM encrypted PAN stored; CVV discarded immediately
  6. Vault token returned to client for use in completePurchase
"""
import re
import secrets
import graphene
from graphene_django import DjangoObjectType

from .models import CardVaultEntry, PaymentAuditLog
from .crypto import rsa_decrypt_payload, aes_encrypt, get_rsa_public_key_pem
from .validators import luhn_check, detect_card_brand, validate_expiry


class CardVaultEntryType(DjangoObjectType):
    class Meta:
        model = CardVaultEntry
        fields = ['id', 'token', 'pan_last_four', 'pan_bin',
                  'card_brand', 'is_default', 'is_active', 'created_at']


class CardVaultQuery(graphene.ObjectType):
    my_vault_cards     = graphene.List(CardVaultEntryType)
    payment_public_key = graphene.String()

    def resolve_my_vault_cards(self, info):
        u = info.context.user
        if u.is_anonymous:
            raise Exception('Not authenticated')
        return CardVaultEntry.objects.filter(customer=u, is_active=True)

    def resolve_payment_public_key(self, info):
        """Return the RSA public key for client-side card encryption."""
        return get_rsa_public_key_pem()


class TokenizeCardMutation(graphene.Mutation):
    """
    Accepts RSA-OAEP encrypted JSON payload from the browser.
    Validates card data, stores AES-256-GCM encrypted PAN.
    CVV is validated for format only and immediately discarded.
    Returns a vault token safe to pass to completePurchase.
    """

    class Arguments:
        encrypted_payload = graphene.String(required=True)
        is_default        = graphene.Boolean()

    token      = graphene.String()
    last_four  = graphene.String()
    card_brand = graphene.String()
    success    = graphene.Boolean()
    error      = graphene.String()

    @classmethod
    def mutate(cls, root, info, encrypted_payload, is_default=False):
        user = info.context.user
        if user.is_anonymous:
            return cls(success=False, error='Not authenticated')

        try:
            data = rsa_decrypt_payload(encrypted_payload)
        except Exception:
            return cls(success=False, error='Invalid encrypted payload — check RSA encryption')

        pan   = re.sub(r'[\s\-]', '', data.get('pan', ''))
        cvv   = str(data.get('cvv', ''))
        month = int(data.get('expiry_month', 0))
        year  = int(data.get('expiry_year', 0))
        name  = data.get('cardholder_name', '').strip()

        if not luhn_check(pan):
            return cls(success=False, error='Invalid card number')
        if not validate_expiry(month, year):
            return cls(success=False, error='Card has expired')
        if not (3 <= len(cvv) <= 4 and cvv.isdigit()):
            return cls(success=False, error='Invalid CVV')
        if not name:
            return cls(success=False, error='Cardholder name is required')

        brand      = detect_card_brand(pan)
        last_four  = pan[-4:]
        bin_digits = pan[:8] if len(pan) >= 8 else pan[:6]
        token      = secrets.token_urlsafe(48)

        if is_default:
            CardVaultEntry.objects.filter(customer=user, is_default=True).update(is_default=False)

        entry = CardVaultEntry.objects.create(
            token=token,
            customer=user,
            pan_last_four=last_four,
            pan_bin=bin_digits,
            card_brand=brand,
            encrypted_pan=aes_encrypt(pan),
            encrypted_expiry=aes_encrypt(f'{month:02d}/{year}'),
            encrypted_cardholder_name=aes_encrypt(name),
            is_default=is_default,
        )
        # CVV is discarded at this point — it is never stored anywhere

        PaymentAuditLog.objects.create(
            action=PaymentAuditLog.Action.CARD_TOKENIZED,
            actor=user,
            resource_type='card_vault',
            resource_id=str(entry.id),
            ip_address=info.context.META.get('REMOTE_ADDR'),
            metadata={'brand': brand, 'last_four': last_four},
        )

        return cls(token=token, last_four=last_four, card_brand=brand, success=True)


class DeleteVaultCardMutation(graphene.Mutation):
    """Soft-delete a saved card token (sets is_active=False)."""

    class Arguments:
        token = graphene.String(required=True)

    success = graphene.Boolean()

    @classmethod
    def mutate(cls, root, info, token):
        user = info.context.user
        if user.is_anonymous:
            raise Exception('Not authenticated')
        updated = CardVaultEntry.objects.filter(token=token, customer=user).update(is_active=False)
        if updated:
            PaymentAuditLog.objects.create(
                action=PaymentAuditLog.Action.CARD_DELETED,
                actor=user,
                resource_type='card_vault',
                resource_id='',
                ip_address=info.context.META.get('REMOTE_ADDR'),
                metadata={'token_prefix': token[:8]},
            )
        return cls(success=bool(updated))


class SetDefaultCardMutation(graphene.Mutation):
    """Mark a vault card as the default payment method."""

    class Arguments:
        token = graphene.String(required=True)

    success = graphene.Boolean()

    @classmethod
    def mutate(cls, root, info, token):
        user = info.context.user
        if user.is_anonymous:
            raise Exception('Not authenticated')
        CardVaultEntry.objects.filter(customer=user, is_default=True).update(is_default=False)
        updated = CardVaultEntry.objects.filter(
            token=token, customer=user, is_active=True
        ).update(is_default=True)
        return cls(success=bool(updated))


class CardVaultMutation(graphene.ObjectType):
    tokenize_card     = TokenizeCardMutation.Field()
    delete_vault_card = DeleteVaultCardMutation.Field()
    set_default_card  = SetDefaultCardMutation.Field()
