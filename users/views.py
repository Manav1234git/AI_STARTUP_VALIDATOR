from django.contrib.auth import authenticate, login,logout
from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required

def login_view(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        # Check if user exists
        if not User.objects.filter(username=email).exists():
            return render(request, 'users/login.html', {
                'error': 'Account not found. Please create account first.'
            })

        user = authenticate(request, username=email, password=password)

        if user is not None:
            login(request, user)
            return redirect('dashboard')
        else:
            return render(request, 'users/login.html', {
                'error': 'Invalid password'
            })

    return render(request, 'users/login.html')

def register(request):
    if request.method == "POST":

        # 🛑 Only run register if confirm_password exists
        if 'confirm_password' not in request.POST:
            return redirect('/')  # ignore wrong form submission

        email = request.POST.get('email')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')

        if password != confirm_password:
            return render(request, 'users/login.html', {'error': 'Passwords do not match'})

        if User.objects.filter(username=email).exists():
            return render(request, 'users/login.html', {'error': 'User already exists'})

        User.objects.create_user(username=email, password=password)

        return render(request, 'users/login.html', {'success': 'Account created successfully'})

    return render(request, 'users/login.html')

@login_required
def profile(request):
    return render(request, 'users/profile.html')

def settings_view(request):
    return render(request, 'users/settings.html')

def logout_view(request):
    logout(request)
    return redirect('/') 