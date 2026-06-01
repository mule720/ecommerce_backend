from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CardVaultEntry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('token', models.CharField(db_index=True, max_length=64, unique=True)),
                ('pan_last_four', models.CharField(max_length=4)),
                ('pan_bin', models.CharField(max_length=8)),
                ('card_brand', models.CharField(default='unknown', max_length=20)),
                ('encrypted_pan', models.TextField()),
                ('encrypted_expiry', models.TextField()),
                ('encrypted_cardholder_name', models.TextField()),
                ('is_default', models.BooleanField(default=False)),
                ('is_active', models.BooleanField(default=True)),
                ('key_version', models.IntegerField(default=1)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('customer', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='vault_cards',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'db_table': 'card_vault', 'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='PaymentAuditLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('action', models.CharField(
                    choices=[
                        ('card_tokenized',    'Card Tokenized'),
                        ('card_used',         'Card Used for Payment'),
                        ('card_deleted',      'Card Deleted'),
                        ('payment_initiated', 'Payment Initiated'),
                        ('payment_completed', 'Payment Completed'),
                        ('payment_failed',    'Payment Failed'),
                        ('refund_requested',  'Refund Requested'),
                        ('wallet_credited',   'Wallet Credited'),
                        ('wallet_debited',    'Wallet Debited'),
                        ('payout_dispatched', 'Vendor Payout Dispatched'),
                    ],
                    max_length=50,
                )),
                ('resource_type', models.CharField(blank=True, max_length=50)),
                ('resource_id', models.CharField(blank=True, max_length=100)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('actor', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='payment_audit_logs',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'db_table': 'payment_audit_log', 'ordering': ['-created_at']},
        ),
    ]
