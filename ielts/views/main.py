from django.shortcuts import render
from django.contrib.auth.decorators import login_required

from ..models import HomePageContent


@login_required
def home(request):
    content = HomePageContent.objects.filter(is_active=True).first()

    return render(request, "ielts/main.html", {
        "content": content
    })