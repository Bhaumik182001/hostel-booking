from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.db import transaction
from django.http import HttpResponseNotAllowed

from accounts.models import StudentProfile
from rooms.models import Room
from .models import SwapRequest
from .forms import SwapRequestCreateForm


@login_required(login_url='accounts:login')
def create_swap_view(request):
    profile, _ = StudentProfile.objects.get_or_create(user=request.user)

    if not profile.current_room:
        messages.error(request, "You must be allocated to a room before submitting swap requests.")
        return redirect('accounts:dashboard')

    if request.method == 'POST':
        form = SwapRequestCreateForm(request.POST, user=request.user)
        if form.is_valid():
            swap_request = form.save(commit=False)
            swap_request.requester = profile
            swap_request.status = SwapRequest.Status.PENDING
            swap_request.save()

            messages.success(
                request,
                f"Swap request for {swap_request.target_room} submitted successfully!"
            )
            # Post/Redirect/Get (PRG) Pattern
            return redirect('swaps:list')
    else:
        form = SwapRequestCreateForm(user=request.user)

    context = {
        'form': form,
        'current_room': profile.current_room,
    }
    return render(request, 'swaps/create_swap.html', context)


@login_required(login_url='accounts:login')
def my_swaps_list_view(request):
    profile, _ = StudentProfile.objects.get_or_create(user=request.user)

    outgoing_swaps = SwapRequest.objects.filter(
        requester=profile
    ).select_related('target_room__block').order_by('-created_at')

    if profile.current_room:
        incoming_swaps = SwapRequest.objects.filter(
            target_room=profile.current_room
        ).select_related('requester__user', 'requester__current_room__block').order_by('-created_at')
    else:
        incoming_swaps = SwapRequest.objects.none()

    context = {
        'profile': profile,
        'outgoing_swaps': outgoing_swaps,
        'incoming_swaps': incoming_swaps,
    }
    return render(request, 'swaps/my_swaps.html', context)


@login_required(login_url='accounts:login')
@require_POST
def cancel_swap_view(request, swap_id):
    profile = get_object_or_404(StudentProfile, user=request.user)
    swap = get_object_or_404(SwapRequest, pk=swap_id, requester=profile)

    if swap.status == SwapRequest.Status.PENDING:
        swap.status = SwapRequest.Status.REJECTED
        swap.save(update_fields=['status'])
        messages.info(request, f"Swap request #{swap.id} has been cancelled.")
    else:
        messages.warning(request, f"Cannot cancel request with status '{swap.status}'.")

    return redirect('swaps:list')


@login_required(login_url='accounts:login')
def swap_matches_view(request):
    """
    Computes both 1-to-1 Pairwise swaps and 3-Party Circular swaps
    using a directed graph cycle detection algorithm.
    """
    pending_swaps = SwapRequest.objects.filter(
        status=SwapRequest.Status.PENDING
    ).select_related(
        'requester__user',
        'requester__current_room__block',
        'target_room__block'
    )

    # Map (from_room_id, to_room_id) -> list of SwapRequest
    req_by_room_pair = {}
    for req in pending_swaps:
        c_room = req.requester.current_room
        if not c_room:
            continue
        req_by_room_pair.setdefault((c_room.id, req.target_room_id), []).append(req)

    # 1. Pairwise Swap Matching (1-to-1 reciprocity)
    pairwise_matches = []
    seen_pairs = set()

    for (r_a, r_b), reqs_a in req_by_room_pair.items():
        if (r_b, r_a) in req_by_room_pair:
            canonical_key = tuple(sorted([r_a, r_b]))
            if canonical_key in seen_pairs:
                continue
            seen_pairs.add(canonical_key)

            reqs_b = req_by_room_pair[(r_b, r_a)]
            for ra in reqs_a:
                for rb in reqs_b:
                    pairwise_matches.append({
                        'req_a': ra,
                        'req_b': rb,
                        'student_a': ra.requester,
                        'student_b': rb.requester,
                        'room_a': ra.requester.current_room,
                        'room_b': rb.requester.current_room,
                        'involves_user': request.user.id in [ra.requester.user_id, rb.requester.user_id],
                    })

    # 2. Multi-Party Circular Swap Matching (3-Party graph cycle detection)
    circular_matches = []
    seen_cycles = set()

    room_graph = {}
    for (r_from, r_to) in req_by_room_pair.keys():
        room_graph.setdefault(r_from, set()).add(r_to)

    for r_a in room_graph:
        for r_b in room_graph.get(r_a, set()):
            if r_b == r_a:
                continue
            for r_c in room_graph.get(r_b, set()):
                if r_c == r_a or r_c == r_b:
                    continue
                if r_a in room_graph.get(r_c, set()):
                    # Found 3-party cycle: r_a -> r_b -> r_c -> r_a
                    cycle = [r_a, r_b, r_c]
                    min_idx = cycle.index(min(cycle))
                    canon = tuple(cycle[min_idx:] + cycle[:min_idx])
                    if canon in seen_cycles:
                        continue
                    seen_cycles.add(canon)

                    ca, cb, cc = canon
                    rab = req_by_room_pair[(ca, cb)][0]
                    rbc = req_by_room_pair[(cb, cc)][0]
                    rca = req_by_room_pair[(cc, ca)][0]

                    circular_matches.append({
                        'req_ab': rab,
                        'req_bc': rbc,
                        'req_ca': rca,
                        'student_a': rab.requester,
                        'student_b': rbc.requester,
                        'student_c': rca.requester,
                        'room_a': rab.requester.current_room,
                        'room_b': rbc.requester.current_room,
                        'room_c': rca.requester.current_room,
                        'involves_user': request.user.id in [
                            rab.requester.user_id,
                            rbc.requester.user_id,
                            rca.requester.user_id,
                        ],
                    })

    context = {
        'pairwise_matches': pairwise_matches,
        'circular_matches': circular_matches,
    }
    return render(request, 'swaps/matches.html', context)


@login_required(login_url='accounts:login')
@require_POST
def execute_swap_view(request, swap_id):
    """
    Executes room reassignments inside atomic database transaction
    to prevent race conditions.
    """
    swap_a = get_object_or_404(
        SwapRequest.objects.select_related(
            'requester__user', 'requester__current_room', 'target_room'
        ),
        pk=swap_id,
        status=SwapRequest.Status.PENDING,
    )
    student_a = swap_a.requester
    room_a = student_a.current_room
    room_b = swap_a.target_room

    if not room_a:
        messages.error(request, "Student profile does not have an allocated current room.")
        return redirect('swaps:matches')

    # Case 1: Pairwise 1-to-1 reciprocal swap
    swap_b = SwapRequest.objects.filter(
        requester__current_room=room_b,
        target_room=room_a,
        status=SwapRequest.Status.PENDING,
    ).select_related('requester__user').first()

    if swap_b:
        student_b = swap_b.requester
        with transaction.atomic():
            student_a.current_room = room_b
            student_b.current_room = room_a
            student_a.save(update_fields=['current_room'])
            student_b.save(update_fields=['current_room'])

            swap_a.status = SwapRequest.Status.COMPLETED
            swap_b.status = SwapRequest.Status.COMPLETED
            swap_a.save(update_fields=['status'])
            swap_b.save(update_fields=['status'])

            messages.success(
                request,
                f"Pairwise swap executed! {student_a.user.username} (Room {room_b.room_number}) "
                f"<-> {student_b.user.username} (Room {room_a.room_number})."
            )
            return redirect('swaps:matches')

    # Case 2: 3-Party circular cycle swap
    swap_b = SwapRequest.objects.filter(
        requester__current_room=room_b,
        status=SwapRequest.Status.PENDING,
    ).select_related('requester__user', 'target_room').first()

    if swap_b and swap_b.target_room:
        room_c = swap_b.target_room
        swap_c = SwapRequest.objects.filter(
            requester__current_room=room_c,
            target_room=room_a,
            status=SwapRequest.Status.PENDING,
        ).select_related('requester__user').first()

        if swap_c:
            student_b = swap_b.requester
            student_c = swap_c.requester
            with transaction.atomic():
                student_a.current_room = room_b
                student_b.current_room = room_c
                student_c.current_room = room_a

                student_a.save(update_fields=['current_room'])
                student_b.save(update_fields=['current_room'])
                student_c.save(update_fields=['current_room'])

                swap_a.status = SwapRequest.Status.COMPLETED
                swap_b.status = SwapRequest.Status.COMPLETED
                swap_c.status = SwapRequest.Status.COMPLETED
                swap_a.save(update_fields=['status'])
                swap_b.save(update_fields=['status'])
                swap_c.save(update_fields=['status'])

                messages.success(
                    request,
                    f"3-Party circular swap executed! "
                    f"{student_a.user.username} -> Room {room_b.room_number}, "
                    f"{student_b.user.username} -> Room {room_c.room_number}, "
                    f"{student_c.user.username} -> Room {room_a.room_number}."
                )
                return redirect('swaps:matches')

    # Case 3: Reallocation to a room with vacant capacity
    if room_b.occupants.count() < room_b.capacity:
        with transaction.atomic():
            student_a.current_room = room_b
            student_a.save(update_fields=['current_room'])
            swap_a.status = SwapRequest.Status.COMPLETED
            swap_a.save(update_fields=['status'])

            messages.success(
                request,
                f"Swap request #{swap_a.id} completed. {student_a.user.username} reassigned to Room {room_b.room_number}."
            )
            return redirect('swaps:matches')

    messages.warning(request, "No eligible reciprocal match or vacant spot currently available for this swap.")
    return redirect('swaps:matches')
