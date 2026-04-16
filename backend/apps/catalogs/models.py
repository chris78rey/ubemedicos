from django.db import models


class Specialty(models.Model):
    name = models.CharField(max_length=150, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "catalogs_specialty"
        ordering = ["name"]

    def __str__(self):
        return self.name
