from django.contrib import admin
from .models import User, Product, Order


class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'role', 'business_category')
    list_filter = ('role',)
    search_fields = ('username', 'email', 'phone')
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal Info', {
            'fields': ('first_name', 'last_name', 'email', 'bio', 'website', 'profile_picture')
        }),
        ('Business Info', {
            'fields': ('business_category', 'location', 'phone'),
            'classes': ('collapse',),
        }),
        ('Permissions', {'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
    )


class ProductAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'seller', 'price', 'category', 'created_at')
    list_filter = ('category', 'seller')
    search_fields = ('name', 'description', 'seller__username')


class OrderAdmin(admin.ModelAdmin):
    # ✅ 'tracking_number' REMOVED from list_display
    list_display = ('id', 'buyer', 'seller', 'product_name', 'total_amount', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('buyer__username', 'seller__username', 'product_name', 'full_name', 'phone')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Order Information', {
            'fields': ('buyer', 'seller', 'product', 'product_name', 'product_price', 'status')
        }),
        ('Customer Details', {
            'fields': ('full_name', 'phone', 'email', 'address', 'city', 'pincode')
        }),
        ('Product Details', {
            'fields': ('size', 'quantity', 'order_notes')
        }),
        ('Pricing', {
            'fields': ('platform_fee', 'shipping_charge', 'total_amount')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )


admin.site.register(User, UserAdmin)
admin.site.register(Product, ProductAdmin)
admin.site.register(Order, OrderAdmin)

from .models import User, Product, Order, Notification

class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'notification_type', 'title', 'amount', 'is_read', 'created_at')
    list_filter = ('notification_type', 'is_read', 'created_at')
    search_fields = ('user__username', 'title', 'message')
    readonly_fields = ('created_at',)

admin.site.register(Notification, NotificationAdmin)

from .models import User, Product, Order, Notification, Dispute


class DisputeAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'buyer', 'status', 'ai_final_score', 'ai_verdict', 'created_at')
    list_filter = ('status', 'ai_verdict', 'created_at')
    search_fields = ('buyer__username', 'order__tracking_number', 'reason')
    readonly_fields = ('ai_image_score', 'ai_text_score', 'ai_final_score', 'ai_verdict',
                       'ai_matched_keywords', 'ai_analyzed_at', 'ai_similarity_percent',
                       'created_at', 'reviewed_at')


admin.site.register(Dispute, DisputeAdmin)