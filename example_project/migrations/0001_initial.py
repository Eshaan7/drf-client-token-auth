# Generated by Django 3.2.3 on 2021-05-19 08:31

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("durin", "0002_client_throttlerate"),
    ]

    operations = [
        migrations.CreateModel(
            name="ClientSettings",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("description", models.TextField()),
                (
                    "client",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="settings",
                        to="durin.client",
                    ),
                ),
            ],
        ),
    ]
