from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user_service', '0003_otpverification_deliveryaddress_otplog'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='deliveryaddress',
            unique_together=set(),
        ),
        migrations.AddConstraint(
            model_name='deliveryaddress',
            constraint=models.UniqueConstraint(
                condition=models.Q(('is_default', True)),
                fields=('user',),
                name='unique_default_delivery_address_per_user',
            ),
        ),
    ]
