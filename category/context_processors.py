from .models import Category
from store.models import Product  

def menu_links(request):
    links = Category.objects.all()
    
    available_genders = Product.objects.filter(is_available=True).values_list('gender', flat=True).distinct()
    
    return {
        'links': links,
        'available_genders': available_genders, 
    }