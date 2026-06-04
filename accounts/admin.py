from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Account, UserProfile
from django.utils.html import format_html

# Register your models here.
class AccountAdmin(UserAdmin):
    list_display = ('email', 'first_name','last_name', 'username', 'last_login','date_joined','is_active')
    list_display_links = ('email','first_name','last_name')
    readonly_fields = ('last_login','date_joined')
    ordering = ('date_joined',)
    filter_horizontal = ()
    list_filter = ()
    fieldsets = ()

class UserProfileAdmin(admin.ModelAdmin):
    def thumbnail(self, object):
        # 1. If the user has uploaded an image, display it normally
        if object.profile_picture:
            return format_html('<img src="{}" width="30" height="30" style="border-radius:50%; object-fit:cover;">'.format(object.profile_picture.url))
        
        # 2. Fallback: Get the first letter of the username (uppercase)
        # We use a fallback 'U' just in case the username field is somehow blank
        first_letter = object.user.username[0].upper() if object.user and object.user.username else 'U'
        
        # 3. Render a clean CSS-styled circle with the letter inside
        return format_html(
            '<div style="'
            'width: 30px; '
            'height: 30px; '
            'border-radius: 50%; '
            'background-color: #4f46e5; ' # Modern indigo color
            'color: white; '
            'display: flex; '
            'align-items: center; '
            'justify-content: center; '
            'font-weight: bold; '
            'font-size: 14px;'
            '">{}</div>',
            first_letter
        )
        
    thumbnail.short_description = 'Profile Picture'
    list_display = ('thumbnail', 'user', 'city', 'state', 'country')


admin.site.register(Account, AccountAdmin)
admin.site.register(UserProfile, UserProfileAdmin)
