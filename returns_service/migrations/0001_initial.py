# Generated manually for returns_service domain split
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('order_service', '0002_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ReturnRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reason', models.CharField(choices=[('defective', 'Defective Product'), ('not_as_described', 'Not As Described'), ('damaged', 'Damaged In Transit'), ('wrong_item', 'Wrong Item Received'), ('changed_mind', 'Changed Mind'), ('size_issue', 'Size/Fit Issue'), ('quality_issue', 'Quality Issue'), ('other', 'Other')], default='other', max_length=50)),
                ('reason_description', models.TextField(blank=True)),
                ('status', models.CharField(choices=[('requested', 'Return Requested'), ('approved', 'Approved'), ('rejected', 'Rejected'), ('shipped_back', 'Shipped Back'), ('received', 'Received'), ('refunded', 'Refunded'), ('cancelled', 'Cancelled')], default='requested', max_length=20)),
                ('refund_amount', models.DecimalField(decimal_places=2, default=Decimal('0.00'), help_text='Amount to be refunded', max_digits=12)),
                ('refund_issued', models.BooleanField(default=False)),
                ('refund_date', models.DateTimeField(blank=True, null=True)),
                ('return_tracking_number', models.CharField(blank=True, max_length=100)),
                ('return_shipping_provider', models.CharField(blank=True, max_length=100)),
                ('return_label_sent', models.BooleanField(default=False)),
                ('return_label_sent_at', models.DateTimeField(blank=True, null=True)),
                ('item_condition', models.CharField(blank=True, choices=[('unused', 'Unused/Original Packaging'), ('used', 'Used - Good Condition'), ('damaged', 'Damaged'), ('defective', 'Defective')], max_length=50)),
                ('admin_notes', models.TextField(blank=True)),
                ('requested_at', models.DateTimeField(auto_now_add=True)),
                ('approved_at', models.DateTimeField(blank=True, null=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='returns_service_return_requests', to=settings.AUTH_USER_MODEL)),
                ('order_item', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='returns', to='order_service.orderitem')),
            ],
            options={
                'db_table': 'returns_service_return_requests',
                'ordering': ['-requested_at'],
            },
        ),
        migrations.CreateModel(
            name='ReturnShipment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tracking_number', models.CharField(max_length=100, unique=True)),
                ('carrier', models.CharField(max_length=100)),
                ('sent_at', models.DateTimeField(auto_now_add=True)),
                ('received_at', models.DateTimeField(blank=True, null=True)),
                ('return_request', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='shipment', to='returns_service.returnrequest')),
            ],
            options={
                'db_table': 'returns_service_return_shipments',
            },
        ),
        migrations.CreateModel(
            name='ReturnHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status_from', models.CharField(max_length=20)),
                ('status_to', models.CharField(max_length=20)),
                ('reason', models.TextField(blank=True)),
                ('changed_at', models.DateTimeField(auto_now_add=True)),
                ('changed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('return_request', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='history', to='returns_service.returnrequest')),
            ],
            options={
                'db_table': 'returns_service_return_history',
                'ordering': ['-changed_at'],
            },
        ),
        migrations.AddIndex(
            model_name='returnrequest',
            index=models.Index(fields=['customer', 'status'], name='returns_ser_cust_st_1df62e_idx'),
        ),
        migrations.AddIndex(
            model_name='returnrequest',
            index=models.Index(fields=['order_item', 'status'], name='returns_ser_order_i_ea55cf_idx'),
        ),
        migrations.AddIndex(
            model_name='returnrequest',
            index=models.Index(fields=['requested_at'], name='returns_ser_reques_6b6a7b_idx'),
        ),
    ]
