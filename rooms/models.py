from django.db import models


class HostelBlock(models.Model):
    class GenderRestriction(models.TextChoices):
        MALE = 'M', 'Male'
        FEMALE = 'F', 'Female'
        COED = 'C', 'Co-ed'

    name = models.CharField(max_length=50, unique=True)
    gender_restriction = models.CharField(
        max_length=1,
        choices=GenderRestriction.choices,
        default=GenderRestriction.COED,
    )

    class Meta:
        verbose_name = 'Hostel Block'
        verbose_name_plural = 'Hostel Blocks'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_gender_restriction_display()})"


class Room(models.Model):
    block = models.ForeignKey(
        HostelBlock,
        on_delete=models.CASCADE,
        related_name='rooms',
    )
    room_number = models.CharField(max_length=10)
    capacity = models.PositiveSmallIntegerField(default=1)

    class Meta:
        verbose_name = 'Room'
        verbose_name_plural = 'Rooms'
        unique_together = ('block', 'room_number')
        ordering = ['block', 'room_number']

    def __str__(self):
        return f"{self.block.name} - Room {self.room_number}"
