from datetime import datetime
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from swaps.models import SwapRequest
from .models import StudentProfile
from .forms import StudentRegistrationForm


def register_view(request):
    if request.user.is_authenticated:
        return redirect('accounts:dashboard')

    if request.method == 'POST':
        form = StudentRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Registration successful. Welcome to the Hostel Platform!')
            return redirect('accounts:dashboard')
    else:
        form = StudentRegistrationForm()
    return render(request, 'accounts/register.html', {'form': form})


def user_login_view(request):
    if request.user.is_authenticated:
        return redirect('accounts:dashboard')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                # Read cookie and persist into session state (Unit VI)
                preferred_block = request.COOKIES.get('preferred_block')
                if preferred_block:
                    request.session['preferred_block'] = preferred_block

                messages.info(request, f'Welcome back, {user.username}!')
                next_url = request.GET.get('next')
                if next_url:
                    return redirect(next_url)
                return redirect('accounts:dashboard')
    else:
        form = AuthenticationForm(request)
    return render(request, 'accounts/login.html', {'form': form})


def user_logout_view(request):
    logout(request)
    messages.info(request, 'You have been successfully logged out.')
    return redirect('accounts:login')


@login_required(login_url='accounts:login')
def student_dashboard_view(request):
    # Session state tracking (Visits counter & Activity timestamp)
    account_visits = request.session.get('account_visits', 0) + 1
    request.session['account_visits'] = account_visits
    request.session['last_activity'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Retrieve profile and room/swap details
    profile, _ = StudentProfile.objects.get_or_create(user=request.user)
    assigned_room = profile.current_room
    pending_swaps = profile.swap_requests.filter(status=SwapRequest.Status.PENDING)

    context = {
        'profile': profile,
        'assigned_room': assigned_room,
        'pending_swaps': pending_swaps,
        'account_visits': account_visits,
        'last_activity': request.session.get('last_activity'),
        'preferred_block_session': request.session.get('preferred_block', 'Not Set'),
        'preferred_block_cookie': request.COOKIES.get('preferred_block', 'Not Set'),
    }
    return render(request, 'accounts/dashboard.html', context)


def set_preference_cookie_view(request):
    preferred_block = request.GET.get('preferred_block', 'Block-A')
    redirect_target = request.GET.get('next') or request.META.get('HTTP_REFERER') or 'accounts:dashboard'
    response = redirect(redirect_target)

    # Set cookie with 7 days expiration (60s * 60m * 24h * 7d)
    response.set_cookie(
        'preferred_block',
        preferred_block,
        max_age=7 * 24 * 60 * 60,
        httponly=False,
        samesite='Lax',
    )
    messages.success(request, f"Cookie 'preferred_block' updated to '{preferred_block}'.")
    return response
