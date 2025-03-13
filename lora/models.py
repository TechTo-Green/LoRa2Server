# models.py
from django.db import models


class AppConfig(models.Model):
    exp_keys = models.JSONField(default=list)
    host = models.CharField(max_length=255, default='')
    baud_rate = models.IntegerField(default=9600)
    serial_port = models.CharField(max_length=255, default='')

    class Meta:
        verbose_name = "Application Configuration"
        verbose_name_plural = "Application Configurations"

    @classmethod
    def get_config(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
