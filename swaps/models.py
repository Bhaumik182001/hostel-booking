from django.db import models


class SwapRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'
        COMPLETED = 'COMPLETED', 'Completed'

    requester = models.ForeignKey(
        'accounts.StudentProfile',
        on_delete=models.CASCADE,
        related_name='swap_requests',
    )
    target_room = models.ForeignKey(
        'rooms.Room',
        on_delete=models.CASCADE,
        related_name='incoming_swap_requests',
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Swap Request'
        verbose_name_plural = 'Swap Requests'
        unique_together = ('requester', 'target_room')
        ordering = ['-created_at']

    def __str__(self):
        return f"Swap #{self.id}: {self.requester.user.username} -> {self.target_room} [{self.status}]"
