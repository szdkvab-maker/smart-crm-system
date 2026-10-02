from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('register/', views.client_registration, name='client_registration'),
    path('portal/', views.portal_dashboard, name='portal_dashboard'),
    path('portal/requests/<str:kind>/new/', views.portal_request_create, name='portal_request_create'),
    path('management/requests/', views.manage_requests, name='manage_requests'),
    path('management/registrations/<int:pk>/<str:decision>/', views.review_registration, name='review_registration'),
    path('management/requests/<int:pk>/<str:decision>/', views.review_portal_request, name='review_portal_request'),
]
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
