from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from .models import Client, Deal, Task
from .forms import ClientForm, DealForm, TaskForm

RESOURCES = {
    'clients': (Client, ClientForm, 'Клиенты'),
    'deals': (Deal, DealForm, 'Сделки'),
    'tasks': (Task, TaskForm, 'Задачи'),
}


@login_required
def dashboard(request):
    return render(request, 'crm/dashboard.html', {
        'client_count': Client.objects.filter(owner=request.user).count(),
        'deal_count': Deal.objects.filter(owner=request.user, status__in=['new', 'in_progress']).count(),
        'task_count': Task.objects.filter(owner=request.user, is_completed=False).count(),
        'revenue': Deal.objects.filter(owner=request.user, status='won').aggregate(total=Sum('amount'))['total'] or 0,
    })


@login_required
def listing(request, kind):
    model, _, title = RESOURCES[kind]
    objects = model.objects.filter(owner=request.user)
    q = request.GET.get('q', '').strip()
    if kind == 'clients' and q:
        objects = objects.filter(Q(name__icontains=q) | Q(company__icontains=q) | Q(email__icontains=q) | Q(phone__icontains=q))
    elif q:
        objects = objects.filter(title__icontains=q)
    status = request.GET.get('status', '')
    if kind == 'deals' and status in Deal.Status.values:
        objects = objects.filter(status=status)
    if kind == 'tasks' and status in ['open', 'done']:
        objects = objects.filter(is_completed=status == 'done')
    if kind != 'clients':
        objects = objects.select_related('client')
    return render(request, 'crm/list.html', {'objects': objects, 'kind': kind, 'title': title, 'q': q, 'status': status, 'statuses': Deal.Status.choices})


@login_required
def edit(request, kind, pk=None):
    model, form_class, title = RESOURCES[kind]
    instance = get_object_or_404(model, pk=pk, owner=request.user) if pk else None
    form = form_class(request.POST if request.method == 'POST' else None, instance=instance)
    if 'client' in form.fields:
        form.fields['client'].queryset = Client.objects.filter(owner=request.user)
    if request.method == 'POST' and form.is_valid():
        obj = form.save(commit=False)
        obj.owner = request.user
        obj.save()
        messages.success(request, 'Изменения сохранены.')
        return redirect(kind + '_list')
    return render(request, 'crm/form.html', {'form': form, 'title': title, 'kind': kind})


@login_required
def delete(request, kind, pk):
    model, _, title = RESOURCES[kind]
    obj = get_object_or_404(model, pk=pk, owner=request.user)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, 'Запись удалена.')
        return redirect(kind + '_list')
    return render(request, 'crm/delete.html', {'object': obj, 'kind': kind, 'title': title})
