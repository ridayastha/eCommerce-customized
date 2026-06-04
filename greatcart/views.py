from django.shortcuts import render
from store.models import Product
from django.db.models import Avg, Count

def home(request):
    # 1. Random Section (Shuffled)
    random_products = Product.objects.filter(is_available=True).order_by('?')[:10]

    # 2. Latest Upload Section (Newest first)
    latest_products = Product.objects.filter(is_available=True).order_by('-created_date')[:8]

    # 3. Highest Rated (Calculated by average review score)
    highest_rated = Product.objects.filter(is_available=True).annotate(
        db_rating=Avg('reviewrating__rating')
    ).order_by('-db_rating')[:4]

    # 4. Recommended (Based on products with the most reviews)
    recommended = Product.objects.filter(is_available=True).annotate(
        review_count=Count('reviewrating')
    ).order_by('-review_count')[:4]

    context = {
        'random_products': random_products,
        'latest_products': latest_products,
        'highest_rated': highest_rated,
        'recommended': recommended,
    }
    return render(request, 'home.html', context)