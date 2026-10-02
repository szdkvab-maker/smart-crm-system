from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum, Count, F, Prefetch
from django.core.paginator import Paginator
from django.http import FileResponse, Http404
from django.utils import timezone
from datetime import timedelta
from functools import wraps
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpResponseForbidden
from django.views.decorators.http import require_POST
from .models import (
    Client, ClientPortalProfile, Deal, PortalRequest, RegistrationRequest, Task,
)
from .forms import (
    ClientForm, ClientRegistrationForm, DealForm, PortalDealRequestForm,
    PortalTaskRequestForm, TaskForm,
)

RESOURCES = {
    'clients': (Client, ClientForm, 'Клиенты'),
    'deals': (Deal, DealForm, 'Сделки'),
    'tasks': (Task, TaskForm, 'Задачи'),
}


def crm_user_required(view):
    @login_required
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if hasattr(request.user, 'portal_profile'):
            return redirect('portal_dashboard')
        return view(request, *args, **kwargs)
    return wrapped


def portal_user_required(view):
    @login_required
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not hasattr(request.user, 'portal_profile') or not request.user.portal_profile.client_id:
            return redirect('dashboard')
        return view(request, *args, **kwargs)
    return wrapped


def staff_user_required(view):
    @login_required
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_staff:
            return HttpResponseForbidden()
        return view(request, *args, **kwargs)
    return wrapped


@crm_user_required
def dashboard(request):
    deals = Deal.objects.filter(owner=request.user)
    tasks = Task.objects.filter(owner=request.user, is_completed=False)
    today = timezone.localdate()
    funnel_counts = dict(deals.values_list('status').annotate(count=Count('pk')))
    return render(request, 'crm/dashboard.html', {
        'client_count': Client.objects.filter(owner=request.user).count(),
        'deal_count': Deal.objects.filter(owner=request.user, status__in=['new', 'in_progress']).count(),
        'task_count': Task.objects.filter(owner=request.user, is_completed=False).count(),
        'revenue': Deal.objects.filter(owner=request.user, status='won').aggregate(total=Sum('amount'))['total'] or 0,
        'won_count': deals.filter(status='won').count(),
        'today_count': tasks.filter(due_date=today).count(),
        'overdue_count': tasks.filter(due_date__lt=today).count(),
        'upcoming_tasks': tasks.order_by(F('due_date').asc(nulls_last=True), '-created_at')[:5],
        'recent_deals': deals.select_related('client')[:5],
        'funnel': [
            {'label': label, 'status': status, 'count': funnel_counts.get(status, 0),
             'width': round(funnel_counts.get(status, 0) / max(1, sum(funnel_counts.values())) * 100)}
            for status, label in Deal.Status.choices
        ],
        'today': today,
    })


@crm_user_required
def listing(request, kind):
    model, _, title = RESOURCES[kind]
    objects = model.objects.filter(owner=request.user)
    q = request.GET.get('q', '').strip()
    if kind == 'clients' and q:
        objects = objects.filter(Q(name__icontains=q) | Q(company__icontains=q) | Q(email__icontains=q) | Q(phone__icontains=q))
    elif q:
        objects = objects.filter(title__icontains=q)
    status = request.GET.get('status', '')
    if kind == 'deals' and status == 'active':
        objects = objects.filter(status__in=['new', 'in_progress'])
    if kind == 'deals' and status in Deal.Status.values:
        objects = objects.filter(status=status)
    if kind == 'tasks' and status in ['open', 'done']:
        objects = objects.filter(is_completed=status == 'done')
    if kind == 'tasks':
        today = timezone.localdate()
        period = request.GET.get('period', '')
        if period == 'today':
            objects = objects.filter(due_date=today, is_completed=False)
        elif period == 'overdue':
            objects = objects.filter(due_date__lt=today, is_completed=False)
        elif period == 'week':
            objects = objects.filter(due_date__range=(today, today + timedelta(days=6)), is_completed=False)
    if kind == 'clients':
        client_type = request.GET.get('type', '')
        if client_type in Client.Kind.values:
            objects = objects.filter(kind=client_type)
        sort = request.GET.get('sort', 'recent')
        objects = objects.order_by({'name': 'name', 'oldest': 'created_at'}.get(sort, '-created_at'), 'pk')
        objects = objects.prefetch_related(
            Prefetch('deals', queryset=Deal.objects.filter(owner=request.user), to_attr='visible_deals'),
            Prefetch('tasks', queryset=Task.objects.filter(owner=request.user, is_completed=False).order_by(F('due_date').asc(nulls_last=True)), to_attr='visible_tasks'),
        )
        page = Paginator(objects, 12).get_page(request.GET.get('page'))
        for obj in page:
            obj.deal_total = sum(deal.amount for deal in obj.visible_deals)
        params = request.GET.copy()
        params.pop('page', None)
        return render(request, 'crm/clients.html', {
            'objects': page, 'page_obj': page, 'kind': kind, 'title': title, 'q': q,
            'client_type': client_type, 'sort': sort, 'query_string': params.urlencode(),
            'mode': 'table' if request.GET.get('mode') == 'table' else 'cards',
        })
    if kind != 'clients':
        objects = objects.select_related('client')
    return render(request, 'crm/list.html', {'objects': objects, 'kind': kind, 'title': title, 'q': q, 'status': status, 'statuses': Deal.Status.choices, 'today': timezone.localdate()})


@crm_user_required
def edit(request, kind, pk=None):
    model, form_class, title = RESOURCES[kind]
    instance = get_object_or_404(model, pk=pk, owner=request.user) if pk else None
    form = form_class(request.POST if request.method == 'POST' else None,
                      request.FILES if request.method == 'POST' else None, instance=instance)
    if 'client' in form.fields:
        form.fields['client'].queryset = Client.objects.filter(owner=request.user)
    if request.method == 'POST' and form.is_valid():
        obj = form.save(commit=False)
        obj.owner = request.user
        obj.save()
        messages.success(request, 'Изменения сохранены.')
        return redirect(kind + '_list')
    return render(request, 'crm/form.html', {'form': form, 'title': title, 'kind': kind, 'instance': instance})


@crm_user_required
def client_detail(request, pk):
    obj = get_object_or_404(Client, pk=pk, owner=request.user)
    context = {
        'customer': obj, 'kind': 'clients', 'title': obj.name,
        'deals': obj.deals.filter(owner=request.user),
        'tasks': obj.tasks.filter(owner=request.user),
    }
    template = 'crm/client_panel.html' if request.GET.get('panel') == '1' else 'crm/client_detail.html'
    return render(request, template, context)


@crm_user_required
def client_photo(request, pk):
    obj = get_object_or_404(Client, pk=pk, owner=request.user)
    if not obj.photo:
        raise Http404
    try:
        response = FileResponse(obj.photo.open('rb'), content_type='image/jpeg')
    except FileNotFoundError:
        raise Http404
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@crm_user_required
def delete(request, kind, pk):
    model, _, title = RESOURCES[kind]
    obj = get_object_or_404(model, pk=pk, owner=request.user)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, 'Запись удалена.')
        return redirect(kind + '_list')
    return render(request, 'crm/delete.html', {'object': obj, 'kind': kind, 'title': title})


def client_registration(request):
    if request.user.is_authenticated:
        return redirect('portal_dashboard' if hasattr(request.user, 'portal_profile') else 'dashboard')
    form = ClientRegistrationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Заявка на регистрацию отправлена. Дождитесь решения администратора.')
        return redirect('login')
    return render(request, 'registration/register.html', {'form': form, 'title': 'Регистрация'})


@portal_user_required
def portal_dashboard(request):
    requests = PortalRequest.objects.filter(requester=request.user)
    return render(request, 'crm/portal.html', {
        'title': 'Кабинет клиента',
        'requests': requests,
    })


@portal_user_required
def portal_request_create(request, kind):
    if kind == PortalRequest.Kind.DEAL:
        form_class = PortalDealRequestForm
        title = 'Заявка на сделку'
    elif kind == PortalRequest.Kind.TASK:
        form_class = PortalTaskRequestForm
        title = 'Заявка на задачу'
    else:
        raise Http404
    form = form_class(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        portal_request = form.save(commit=False)
        portal_request.requester = request.user
        portal_request.kind = kind
        portal_request.save()
        messages.success(request, 'Заявка отправлена администратору.')
        return redirect('portal_dashboard')
    return render(request, 'crm/portal_request_form.html', {
        'form': form,
        'title': title,
    })


@staff_user_required
def manage_requests(request):
    return render(request, 'crm/manage_requests.html', {
        'title': 'Заявки клиентов',
        'registrations': RegistrationRequest.objects.select_related('user').all(),
        'requests': PortalRequest.objects.select_related(
            'requester', 'requester__portal_profile', 'requester__portal_profile__client',
            'reviewed_by', 'resulting_deal', 'resulting_task',
        ).all(),
    })


@staff_user_required
@require_POST
@transaction.atomic
def review_registration(request, pk, decision):
    registration = get_object_or_404(RegistrationRequest, pk=pk)
    if registration.status != RegistrationRequest.Status.PENDING:
        return redirect('manage_requests')
    if decision == 'approve':
        user = registration.user
        client = Client.objects.create(
            owner=request.user,
            name=registration.full_name,
            email=user.email,
            phone=registration.phone,
            company=registration.company,
        )
        profile, _ = ClientPortalProfile.objects.get_or_create(user=user)
        profile.client = client
        profile.save(update_fields=['client'])
        user.is_active = True
        user.save(update_fields=['is_active'])
        registration.status = RegistrationRequest.Status.APPROVED
        messages.success(request, f'Регистрация {user.username} одобрена.')
    elif decision == 'reject':
        registration.status = RegistrationRequest.Status.REJECTED
        messages.success(request, f'Регистрация {registration.user.username} отклонена.')
    else:
        raise Http404
    registration.reviewed_by = request.user
    registration.reviewed_at = timezone.now()
    registration.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])
    return redirect('manage_requests')


@staff_user_required
@require_POST
@transaction.atomic
def review_portal_request(request, pk, decision):
    portal_request = get_object_or_404(PortalRequest, pk=pk)
    if portal_request.status != PortalRequest.Status.PENDING:
        return redirect('manage_requests')
    if decision == 'approve':
        profile = get_object_or_404(ClientPortalProfile, user=portal_request.requester, client__isnull=False)
        client = profile.client
        if portal_request.kind == PortalRequest.Kind.DEAL:
            deal = Deal.objects.create(
                owner=client.owner,
                client=client,
                title=portal_request.title,
                amount=portal_request.amount or 0,
            )
            portal_request.resulting_deal = deal
        else:
            task = Task.objects.create(
                owner=client.owner,
                client=client,
                title=portal_request.title,
                description=portal_request.description,
                due_date=portal_request.due_date,
            )
            portal_request.resulting_task = task
        portal_request.status = PortalRequest.Status.APPROVED
        messages.success(request, 'Заявка одобрена, запись добавлена в CRM.')
    elif decision == 'reject':
        portal_request.status = PortalRequest.Status.REJECTED
        messages.success(request, 'Заявка отклонена.')
    else:
        raise Http404
    portal_request.reviewed_by = request.user
    portal_request.reviewed_at = timezone.now()
    portal_request.save(update_fields=[
        'status', 'reviewed_by', 'reviewed_at', 'resulting_deal', 'resulting_task',
    ])
    return redirect('manage_requests')
