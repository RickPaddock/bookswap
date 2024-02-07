# Generated by Django 5.0.1 on 2024-02-07 19:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("books", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="book",
            name="authors",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="book",
            name="description",
            field=models.CharField(blank=True, max_length=500),
        ),
    ]
