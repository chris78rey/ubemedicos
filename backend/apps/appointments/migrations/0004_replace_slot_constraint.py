from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):

    dependencies = [
        ("appointments", "0003_initial"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="appointment",
            name="uq_professional_slot_once",
        ),
        migrations.AddConstraint(
            model_name="appointment",
            constraint=models.UniqueConstraint(
                condition=Q(status__in=["pending_confirmation", "confirmed"]),
                fields=("professional", "scheduled_at"),
                name="uq_professional_slot_active_only",
            ),
        ),
    ]
