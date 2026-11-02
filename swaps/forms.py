from django import forms
from .models import SwapRequest
from rooms.models import Room


class SwapRequestCreateForm(forms.ModelForm):
    class Meta:
        model = SwapRequest
        fields = ['target_room']
        widgets = {
            'target_room': forms.Select(attrs={
                'class': 'form-control',
                'style': 'width: 100%; padding: 0.6rem; border: 1px solid var(--border); border-radius: var(--radius); font-size: 0.95rem;',
            }),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        self.fields['target_room'].queryset = (
            Room.objects.all().select_related('block').order_by('block__name', 'room_number')
        )

    def clean_target_room(self):
        target_room = self.cleaned_data.get('target_room')
        if not target_room:
            raise forms.ValidationError("Please select a valid target room.")

        profile = getattr(self.user, 'student_profile', None)

        # 1. Requester must have an assigned room
        if not profile or not profile.current_room:
            raise forms.ValidationError(
                "You must have an allocated room before requesting a swap."
            )

        current_room = profile.current_room

        # 2. Cannot request swap to own current room
        if target_room == current_room:
            raise forms.ValidationError(
                "You cannot request a swap to your own current room."
            )

        # 3. Gender restriction validation across blocks
        current_block = current_room.block
        target_block = target_room.block

        if target_block.gender_restriction != 'C':
            if current_block.gender_restriction != 'C' and target_block.gender_restriction != current_block.gender_restriction:
                raise forms.ValidationError(
                    f"Gender policy mismatch: Cannot swap between a {current_block.get_gender_restriction_display()} block and a {target_block.get_gender_restriction_display()} block."
                )

        # 4. Duplicate PENDING request validation
        duplicate_pending = SwapRequest.objects.filter(
            requester=profile,
            target_room=target_room,
            status=SwapRequest.Status.PENDING,
        ).exists()
        if duplicate_pending:
            raise forms.ValidationError(
                f"You already have an active pending swap request for {target_room}."
            )

        return target_room
