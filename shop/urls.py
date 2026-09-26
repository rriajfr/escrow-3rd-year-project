from django.urls import path
from . import views

urlpatterns = [
    # ============================================ #
    # HOME & AUTHENTICATION                        #
    # ============================================ #
    path('', views.home_view, name='home'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('logout/', views.logout_view, name='logout'),
    path('switch-account/', views.switch_account, name='switch_account'),
    path('switch-account/<int:user_id>/', views.switch_to_account, name='switch_to_account'),
    path('logout-current/', views.logout_current_only, name='logout_current_only'),

    # ============================================ #
    # DASHBOARDS                                   #
    # ============================================ #
    path('dashboard/', views.buyer_dashboard, name='buyer_dashboard'),
    path('seller-dashboard/', views.seller_dashboard, name='seller_dashboard'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),

    # ============================================ #
    # PRODUCTS                                     #
    # ============================================ #
    path('shop/', views.seller_shop, name='shop'),
    path('product/<int:product_id>/', views.product_detail, name='product_detail'),
    path('load-more-products/', views.load_more_products, name='load_more_products'),
    path('add-product/', views.add_product, name='add_product'),

    # ============================================ #
    # CHECKOUT & ORDER                             #
    # ============================================ #
    path('checkout/<int:product_id>/', views.checkout_page, name='checkout'),
    path('order-confirmation/<int:order_id>/', views.order_confirmation, name='order_confirmation'),

    # ============================================ #
    # BUYER TRACKING                               #
    # ============================================ #
    path('track-order/', views.track_order, name='track_order'),
    path('buyer-tracking/', views.buyer_tracking, name='buyer_tracking'),
    path('order-tracking/<int:order_id>/', views.order_tracking_detail, name='order_tracking_detail'),

    # ============================================ #
    # SELLER ORDERS                                #
    # ============================================ #
    path('seller-orders/', views.seller_orders, name='seller_orders'),
    path('update-tracking/<int:order_id>/', views.update_tracking, name='update_tracking'),
    path('seller/buyer/<int:buyer_id>/', views.seller_buyer_detail, name='seller_buyer_detail'),
   path('seller/view-buyer/<int:buyer_id>/', views.seller_view_buyer_dashboard, name='seller_view_buyer_dashboard'),
    # ============================================ #
    # ADMIN ORDERS & USERS                         #
    # ============================================ #
    path('admin-orders/', views.admin_orders, name='admin_orders'),
    path('admin-dashboard/users/', views.admin_user_list, name='admin_user_list'),
    path('admin-dashboard/user/<int:user_id>/', views.admin_user_detail, name='admin_user_detail'),
    path('notifications/', views.all_notifications, name='all_notifications'),

    # ============================================ #
    # ESCROW ENGINE (Admin only)                   #
    # ============================================ #
    path('escrow/', views.escrow_dashboard, name='escrow_dashboard'),
    path('escrow/order/<int:order_id>/', views.escrow_order_detail, name='escrow_order_detail'),
    path('escrow/release/<int:order_id>/', views.escrow_release, name='escrow_release'),
    path('escrow/refund/<int:order_id>/', views.escrow_refund, name='escrow_refund'),
    path('escrow/force-refund/<int:order_id>/', views.admin_force_refund, name='admin_force_refund'),

    # ============================================ #
    # NOTIFICATIONS                                #
    # ============================================ #
    path('api/notifications/', views.get_unread_notifications, name='get_unread_notifications'),
    path('api/notifications/read/', views.mark_notifications_read, name='mark_notifications_read'),

    # ============================================ #
    # AI DISPUTE SYSTEM                            #
    # ============================================ #
    path('dispute/raise/<int:order_id>/', views.raise_dispute, name='raise_dispute'),
    path('admin-dashboard/disputes/', views.admin_disputes, name='admin_disputes'),
    path('admin-dashboard/dispute/<int:dispute_id>/', views.admin_dispute_detail, name='admin_dispute_detail'),
    path('admin-dashboard/dispute/<int:dispute_id>/decide/', views.admin_dispute_decide, name='admin_dispute_decide'),

    # ============================================ #
    # 👇 RETURN-TO-SELLER FLOW (THE MISSING PIECE) #
    # ============================================ #
    path('order/return/<int:order_id>/', views.submit_return_tracking, name='submit_return_tracking'),
    path('seller/confirm-return/<int:order_id>/', views.seller_confirm_return, name='seller_confirm_return'),
    path('seller/update-return-status/<int:order_id>/', views.update_return_status, name='update_return_status'),
    path('order/return/<int:order_id>/update-status/', views.buyer_update_return_status, name='buyer_update_return_status'),
    # ============================================ #
    # BUYER DELIVERY CONFIRMATION                  #
    # ============================================ #
    path('order/confirm-product/<int:order_id>/', views.buyer_confirm_product_ok, name='buyer_confirm_product_ok'),
    path('order/confirm-delivery/<int:order_id>/', views.buyer_confirm_delivery, name='buyer_confirm_delivery'),
]