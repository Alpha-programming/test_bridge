from django.core.paginator import Paginator
from django.shortcuts import render
from ..models import Resource


def resource_list(request, type):

    query = request.GET.get('q')

    resources = Resource.objects.filter(type=type)

    if query:
        resources = resources.filter(title__icontains=query)

    paginator = Paginator(resources, 6)  # 6 cards per page
    page = request.GET.get('page')

    resources_page = paginator.get_page(page)

    return render(request, 'ielts/resources/resources.html', {
        'resources': resources_page,
        'type': type
    })


def books(request):
    return resource_list(request, 'book')


def magazines(request):
    return resource_list(request, 'magazine')


def newspapers(request):
    return resource_list(request, 'newspaper')