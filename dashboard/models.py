from django.db import models

class Todo(models.Model):
  title = models.CharField(max_length=100)
  date = models.DateField()
  status = models.BooleanField(default=False)
