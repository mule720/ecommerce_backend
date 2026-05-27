from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('product_service', '0002_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='video',
            field=models.FileField(blank=True, null=True, upload_to='products/videos/'),
        ),
        migrations.AddField(
            model_name='product',
            name='video_url',
            field=models.URLField(blank=True),
        ),
        migrations.AddField(
            model_name='productimage',
            name='external_url',
            field=models.URLField(blank=True),
        ),
        migrations.AlterField(
            model_name='productimage',
            name='image',
            field=models.ImageField(blank=True, null=True, upload_to='products/'),
        ),
        migrations.AddField(
            model_name='productvariant',
            name='color',
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AddField(
            model_name='productvariant',
            name='size',
            field=models.CharField(blank=True, max_length=50),
        ),
    ]
