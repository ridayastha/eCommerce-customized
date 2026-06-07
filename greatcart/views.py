from django.shortcuts import render
from store.models import Product
from django.db.models import Avg, Count

def home(request):
    # 1. Random Section (Shuffled Static Grid)
    random_products = Product.objects.filter(is_available=True).order_by('?')[:8]

    # 2. Latest Upload Section (Newest first slider)
    latest_products = Product.objects.filter(is_available=True).order_by('-created_date')[:8]

    # 3. Highest Rated Slider (Sorted by quality score: high to low)
    # Filter excludes items with 0 reviews so unrated products don't glitch to the top.
    highest_rated = Product.objects.filter(is_available=True) \
                                   .annotate(db_rating=Avg('reviewrating__rating')) \
                                   .filter(db_rating__isnull=False) \
                                   .order_by('-db_rating')[:8]

    # 4. Recommended Slider (Sorted by transaction volume/popularity: most reviewed)
    # Filter excludes items with no engagement footprint.
    recommended = Product.objects.filter(is_available=True) \
                                 .annotate(review_count=Count('reviewrating')) \
                                 .filter(review_count__gt=0) \
                                 .order_by('-review_count')[:8]

    # --- SIMULATION FALLBACK MECHANICS ---
    # If the store is empty or running on a fresh local database with 0 reviews, 
    # these fallbacks fill the rows so your design doesn't show blank sections.
    if not highest_rated.exists():
        highest_rated = Product.objects.filter(is_available=True).order_by('-id')[:8]
        
    if not recommended.exists():
        recommended = Product.objects.filter(is_available=True).order_by('id')[:8]

    context = {
        'random_products': random_products,
        'latest_products': latest_products,
        'highest_rated': highest_rated,
        'recommended': recommended,
    }
    return render(request, 'home.html', context)