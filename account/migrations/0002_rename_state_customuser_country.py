# Generated by Django 5.1.4 on 2025-03-27 09:11

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0001_initial'),
    ]

    operations = [
        migrations.RenameField(
            model_name='customuser',
            old_name='state',
            new_name='country',
        ),
    ]
