from django.urls import path
from . import views

urlpatterns = [path('', views.dashboard, name='dashboard')]
urlpatterns += [
    path('clients/<int:pk>/', views.client_detail, name='clients_detail'),
    path('clients/<int:pk>/photo/', views.client_photo, name='clients_photo'),
]
for kind in views.RESOURCES:
    urlpatterns += [
        path(f'{kind}/', views.listing, {'kind': kind}, name=f'{kind}_list'),
        path(f'{kind}/new/', views.edit, {'kind': kind}, name=f'{kind}_create'),
        path(f'{kind}/<int:pk>/edit/', views.edit, {'kind': kind}, name=f'{kind}_edit'),
        path(f'{kind}/<int:pk>/delete/', views.delete, {'kind': kind}, name=f'{kind}_delete'),
    ]
