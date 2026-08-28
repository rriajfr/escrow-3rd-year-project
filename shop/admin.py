from django.contrib import admin
from .models import User, Product

class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'role', 'business_category', 'location')
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
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )

admin.site.register(User, UserAdmin)
admin.site.register(Product)