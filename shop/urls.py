from django.urls import path
from . import views

urlpatterns = [
    path('home/', views.home_view, name='home'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.buyer_dashboard, name='buyer_dashboard'),
    path('seller-dashboard/', views.seller_dashboard, name='seller_dashboard'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('shop/', views.seller_shop, name='shop'),
    path('product/<int:product_id>/', views.product_detail, name='product_detail'),
    # path('checkout/<int:product_id>/', views.checkout_placeholder, name='checkout'),
    path('load-more-products/', views.load_more_products, name='load_more_products'),
    path('add-product/', views.add_product, name='add_product'),
    path('checkout/<int:product_id>/', views.checkout_page, name='checkout'),
]