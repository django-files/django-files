# Generated by Django 4.2.11 on 2024-05-04 03:14

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('oauth', '0020_userinvites_storage_quota'),
    ]

    operations = [
        migrations.CreateModel(
            name='Google',
            fields=[
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, primary_key=True, serialize=False, to=settings.AUTH_USER_MODEL)),
                ('id', models.CharField(max_length=32, unique=True)),
                ('profile', models.JSONField(blank=True, null=True)),
                ('avatar', models.CharField(blank=True, max_length=32, null=True)),
                ('access_token', models.CharField(blank=True, max_length=32, null=True)),
            ],
            options={
                'verbose_name': 'Google',
                'verbose_name_plural': 'Googles',
            },
        ),
        migrations.AlterField(
            model_name='customuser',
            name='user_avatar_choice',
            field=models.CharField(choices=[('DC', 'Discord'), ('GH', 'Github'), ('GO', 'Google'), ('DF', 'Local/Cloud Storage')], default='DF', max_length=2),
        ),
    ]
