from django.contrib import admin
from .models import Cart, CartItem, Enquiry

# Register your models here.

class CartAdmin(admin.ModelAdmin):
    list_display = ('cart_id', 'date_added')

class CartItemAdmin(admin.ModelAdmin):
    list_display = ('product', 'cart', 'quantity', 'is_active')

class EnquiryAdmin(admin.ModelAdmin):
    list_display = ('enquiry_id', 'name', 'email', 'phone_number', 'grand_total', 'created_at')
    search_fields = ('enquiry_id', 'name', 'email', 'phone_number')
    list_filter = ('created_at',)
    readonly_fields = ('created_at',)


admin.site.register(Cart, CartAdmin)
admin.site.register(CartItem, CartItemAdmin)
admin.site.register(Enquiry, EnquiryAdmin)
