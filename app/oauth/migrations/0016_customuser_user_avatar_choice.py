# Generated by Django 4.2.7 on 2024-03-31 16:26

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('oauth', '0015_remove_customuser_show_setup'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='user_avatar_choice',
            field=models.CharField(choices=[('DC', 'Discord'), ('GH', 'Github'), ('DF', 'Local/Cloud Storage')], default='DF', max_length=2),
        ),
    ]
