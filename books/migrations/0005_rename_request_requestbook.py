# Generated by Django 5.0.1 on 2024-02-18 08:32

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("books", "0004_alter_request_decision"),
    ]

    operations = [
        migrations.RenameModel(
            old_name="Request",
            new_name="RequestBook",
        ),
    ]