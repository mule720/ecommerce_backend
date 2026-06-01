from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
from decimal import Decimal


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('order_service', '__first__'),
    ]

    operations = [
        migrations.CreateModel(
            name='Payment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=12)),
                ('currency', models.CharField(default='ZMW', max_length=3)),
                ('method', models.CharField(choices=[
                    ('credit_card', 'Credit Card'),
                    ('debit_card', 'Debit Card'),
                    ('paypal', 'PayPal'),
                    ('stripe', 'Stripe'),
                    ('bank_transfer', 'Bank Transfer'),
                    ('mobile_money', 'Mobile Money'),
                    ('cash_on_delivery', 'Cash on Delivery'),
                    ('wallet', 'Wallet'),
                ], max_length=30)),
                ('status', models.CharField(choices=[
                    ('pending', 'Pending'),
                    ('processing', 'Processing'),
                    ('completed', 'Completed'),
                    ('failed', 'Failed'),
                    ('refunded', 'Refunded'),
                    ('cancelled', 'Cancelled'),
                ], default='pending', max_length=20)),
                ('transaction_id', models.CharField(blank=True, max_length=100, unique=True)),
                ('payment_gateway_response', models.JSONField(blank=True, default=dict)),
                ('gateway_name', models.CharField(blank=True, max_length=50)),
                ('gateway_transaction_id', models.CharField(blank=True, max_length=100)),
                ('payment_system_reference', models.CharField(blank=True, max_length=120)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('customer', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='payments',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('order', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='payments',
                    to='order_service.order',
                )),
            ],
            options={'db_table': 'payments', 'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='Refund',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=12)),
                ('reason', models.TextField()),
                ('status', models.CharField(choices=[
                    ('pending', 'Pending'),
                    ('processing', 'Processing'),
                    ('completed', 'Completed'),
                    ('failed', 'Failed'),
                ], default='pending', max_length=20)),
                ('transaction_id', models.CharField(max_length=100, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('order', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='refunds',
                    to='order_service.order',
                )),
                ('payment', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='refunds',
                    to='payment_service.payment',
                )),
            ],
            options={'db_table': 'refunds', 'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='SavedPaymentMethod',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('type', models.CharField(max_length=50)),
                ('last_four', models.CharField(max_length=4)),
                ('brand', models.CharField(blank=True, max_length=50)),
                ('expiry_month', models.IntegerField()),
                ('expiry_year', models.IntegerField()),
                ('is_default', models.BooleanField(default=False)),
                ('gateway_token', models.CharField(max_length=100)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('customer', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='payment_methods',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'db_table': 'customer_payment_methods', 'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='VendorPaymentTerms',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('payout_period', models.CharField(choices=[
                    ('instant', 'Instant — wallet credited on delivery confirmation'),
                    ('daily', 'Daily   — batched and paid at end of each day'),
                    ('weekly', 'Weekly  — batched on a configured weekday'),
                    ('monthly', 'Monthly — batched on a configured day each month'),
                ], default='daily', max_length=20)),
                ('payout_day', models.IntegerField(blank=True, null=True)),
                ('platform_fee_percentage', models.DecimalField(decimal_places=2, default=Decimal('2.50'), max_digits=5)),
                ('currency', models.CharField(default='ZMW', max_length=3)),
                ('min_payout_amount', models.DecimalField(decimal_places=2, default=Decimal('1.00'), max_digits=12)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('vendor', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='payment_terms',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Vendor Payment Terms',
                'verbose_name_plural': 'Vendor Payment Terms',
                'db_table': 'vendor_payment_terms',
            },
        ),
        migrations.CreateModel(
            name='VendorPayout',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('source_reference', models.CharField(max_length=100)),
                ('gross_amount', models.DecimalField(decimal_places=2, max_digits=12)),
                ('platform_fee_percentage', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=5)),
                ('currency', models.CharField(default='ZMW', max_length=3)),
                ('vendor_phone', models.CharField(max_length=20)),
                ('status', models.CharField(choices=[
                    ('pending', 'Pending'),
                    ('queued', 'Queued — sent to Payment System'),
                    ('paid', 'Paid — wallet credited'),
                    ('failed', 'Failed'),
                ], default='pending', max_length=20)),
                ('payment_system_reference', models.CharField(blank=True, max_length=120)),
                ('event_trace_id', models.CharField(blank=True, max_length=100)),
                ('failure_reason', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('queued_at', models.DateTimeField(blank=True, null=True)),
                ('processed_at', models.DateTimeField(blank=True, null=True)),
                ('vendor', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='payouts',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('payment_terms', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='payouts',
                    to='payment_service.vendorpaymentterms',
                )),
                ('order_items', models.ManyToManyField(blank=True, to='order_service.orderitem')),
            ],
            options={
                'verbose_name': 'Vendor Payout',
                'verbose_name_plural': 'Vendor Payouts',
                'db_table': 'vendor_payouts',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='vendorpayout',
            index=models.Index(fields=['status', 'created_at'], name='vp_status_created_idx'),
        ),
        migrations.AddIndex(
            model_name='vendorpayout',
            index=models.Index(fields=['vendor', 'status'], name='vp_vendor_status_idx'),
        ),
        migrations.CreateModel(
            name='PaymentIdempotencyKey',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('idempotency_key', models.CharField(db_index=True, max_length=64, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('customer', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='idempotency_keys',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('payment', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='idempotency_record',
                    to='payment_service.payment',
                )),
            ],
            options={'db_table': 'payment_idempotency_keys'},
        ),
    ]
