# Generated by Django 5.0.1 on 2024-02-19 21:25

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("books", "0006_requestbook_reject_reason"),
    ]

    operations = [
        migrations.AlterField(
            model_name="requestbook",
            name="reject_reason",
            field=models.CharField(
                blank=True,
                choices=[
                    ("Book no longer owned", "Book no longer owned"),
                    ("Book already loaned", "Book already loaned"),
                    ("I am currently unavailable", "I am currently unavailable"),
                    ("Other", "Other"),
                ],
                max_length=26,
                null=True,
            ),
        ),
    ]
