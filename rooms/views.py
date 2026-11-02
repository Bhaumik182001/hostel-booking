from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q
from .models import HostelBlock, Room


def room_list_view(request):
    blocks = HostelBlock.objects.all()
    rooms = Room.objects.select_related('block').prefetch_related('occupants')

    # GET query filtering (Unit II HTTP query parameter processing)
    selected_block = request.GET.get('block', '').strip()
    selected_capacity = request.GET.get('capacity', '').strip()

    if selected_block:
        rooms = rooms.filter(block__name__icontains=selected_block)

    if selected_capacity.isdigit():
        rooms = rooms.filter(capacity=int(selected_capacity))

    context = {
        'blocks': blocks,
        'rooms': rooms,
        'selected_block': selected_block,
        'selected_capacity': selected_capacity,
        'total_rooms_count': rooms.count(),
    }
    return render(request, 'rooms/room_list.html', context)


def room_detail_view(request, room_id):
    room = get_object_or_404(
        Room.objects.select_related('block').prefetch_related(
            'occupants__user',
            'incoming_swap_requests__requester__user'
        ),
        pk=room_id
    )
    occupants = room.occupants.all()
    incoming_swaps = room.incoming_swap_requests.all()
    available_spots = max(0, room.capacity - occupants.count())

    context = {
        'room': room,
        'occupants': occupants,
        'incoming_swaps': incoming_swaps,
        'available_spots': available_spots,
        'is_full': occupants.count() >= room.capacity,
    }
    return render(request, 'rooms/room_detail.html', context)


def room_regex_search_view(request, block_code, room_num):
    """
    Demonstrates Unit II Regex URL pattern matching.
    Resolves custom patterns such as /rooms/block/BLK-A/101/ or /rooms/block/North/204/
    """
    clean_code = block_code.replace('BLK-', '').replace('blk-', '').strip()
    room = get_object_or_404(
        Room.objects.select_related('block'),
        Q(block__name__iexact=block_code) | Q(block__name__iexact=clean_code) | Q(block__name__icontains=clean_code),
        room_number=room_num
    )
    return redirect('rooms:room_detail', room_id=room.id)
