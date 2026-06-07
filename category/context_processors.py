from django.db.models import Case, When, Value, CharField
from .models import Category
from store.models import Product  

def menu_links(request):
    links = Category.objects.all()
    
    # 1. Fetch distinct available genders
    genders_queryset = Product.objects.filter(is_available=True).values_list('gender', flat=True).distinct()
    
    # 2. Assign custom weights to enforce your layout rule: Men -> Women -> Kids -> Unisex
    # Lower integer values will be displayed first.
    available_genders = genders_queryset.order_by(
        Case(
            When(gender__iexact='men', then=Value(1)),
            When(gender__iexact='women', then=Value(2)),
            When(gender__iexact='kids', then=Value(3)),
            When(gender__iexact='unisex', then=Value(4)),
            default=Value(5),
            output_field=CharField(),
        )
    )
    
    return {
        'links': links,
        'available_genders': available_genders, 
    }