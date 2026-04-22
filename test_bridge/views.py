from django.shortcuts import redirect,render

def home(request):
    return render(request, 'base.html')

def about(request):
    return render(request, 'about.html')