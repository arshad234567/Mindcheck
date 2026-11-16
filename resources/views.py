from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from screening.permissions import counsellor_required

from .forms import ResourceForm, ResourceSearchForm
from .models import Resource, ResourceCategory


def resource_list(request, category_slug=None):
    """Directory with search (GET), category filter and pagination."""
    resources = Resource.objects.select_related("category")
    category = None
    if category_slug:
        category = get_object_or_404(ResourceCategory, slug=category_slug)
        resources = resources.filter(category=category)

    form = ResourceSearchForm(request.GET or None)
    query = ""
    if form.is_valid():
        query = form.cleaned_data["q"].strip()
        if query:
            resources = resources.filter(
                Q(name__icontains=query) | Q(description__icontains=query)
                | Q(city__icontains=query) | Q(category__name__icontains=query)
            )
        if form.cleaned_data["category"]:
            resources = resources.filter(category=form.cleaned_data["category"])
        if form.cleaned_data["crisis_only"]:
            resources = resources.filter(is_crisis_line=True)
    elif request.GET:
        messages.error(request, "That search could not be understood, so all resources are shown.")

    page = Paginator(resources, 6).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)
    return render(request, "resources/list.html", {
        "page_obj": page, "form": form, "query": query, "category": category,
        "categories": ResourceCategory.objects.all(), "querystring": params.urlencode(),
    })


def resource_detail(request, pk):
    resource = get_object_or_404(Resource.objects.select_related("category", "created_by"), pk=pk)
    related = Resource.objects.filter(category=resource.category).exclude(pk=pk)[:3]
    return render(request, "resources/detail.html", {"resource": resource, "related": related})


@counsellor_required
@require_http_methods(["GET", "POST"])
def resource_create(request):
    form = ResourceForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        resource = form.save(commit=False)
        resource.created_by = request.user
        resource.save()
        messages.success(request, f"'{resource.name}' was added to the directory.")
        return redirect(resource)
    return render(request, "resources/form.html", {"form": form, "title": "Add a resource"})


@counsellor_required
@require_http_methods(["GET", "POST"])
def resource_update(request, pk):
    resource = get_object_or_404(Resource, pk=pk)
    form = ResourceForm(request.POST or None, instance=resource)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"'{resource.name}' was updated.")
        return redirect(resource)
    return render(request, "resources/form.html", {"form": form, "title": f"Edit {resource.name}", "resource": resource})


@counsellor_required
@require_http_methods(["GET", "POST"])
def resource_delete(request, pk):
    resource = get_object_or_404(Resource, pk=pk)
    if request.method == "POST":
        name = resource.name
        resource.delete()
        messages.success(request, f"'{name}' was removed from the directory.")
        return redirect("resources:list")
    return render(request, "resources/confirm_delete.html", {"resource": resource})
