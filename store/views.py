from django.shortcuts import render, get_object_or_404, redirect
from .models import Product, ReviewRating, ProductGallery, Variation
from category.models import Category
from carts.models import CartItem
from django.db.models import Q, Avg
from carts.views import _cart_id
from django.core.paginator import Paginator
from .forms import ReviewForm
from django.contrib import messages
from orders.models import OrderProduct

def store(request, category_slug=None):
    categories = None
    
    # 1. Base Query Pool (Filters only by category)
    base_products = Product.objects.filter(is_available=True)
    if category_slug:
        categories = get_object_or_404(Category, slug=category_slug)
        base_products = base_products.filter(category=categories)

    # 2. Extract Dynamic UI Data HERE (While the product pool is full!)
    # This guarantees your colors and sizes options never disappear from the sidebar.
    all_variations = Variation.objects.filter(is_active=True, product__in=base_products).distinct()
    ui_colors = set(all_variations.filter(variation_category__iexact='color').values_list('variation_value', flat=True))
    ui_sizes = set(all_variations.filter(variation_category__iexact='size').values_list('variation_value', flat=True))

    # 3. Now, create a copy to apply filters to for the main product shelf
    products = base_products

    # 4. Gender Filtering
    gender_filter = request.GET.get('gender')
    if gender_filter and gender_filter in ['men', 'women', 'kids', 'unisex']:
        products = products.filter(gender=gender_filter)
    elif gender_filter in ['men', 'women', 'kids']:
        products = products.filter(gender__in=[gender_filter, 'unisex'])

    # 5. Price Range Filtering
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    if min_price and min_price.strip():
        products = products.filter(price__gte=min_price)
    if max_price and max_price.strip():
        products = products.filter(price__lte=max_price)

    # 6. Deep Variation Filtering (Using iexact to defend against case sensitivity)
    selected_colors = request.GET.getlist('color')
    selected_sizes = request.GET.getlist('size')

    if selected_colors:
        products = products.filter(
            variation__variation_category__iexact='color', 
            variation__variation_value__in=selected_colors, 
            variation__is_active=True
        )
    if selected_sizes:
        products = products.filter(
            variation__variation_category__iexact='size', 
            variation__variation_value__in=selected_sizes, 
            variation__is_active=True
        )

    # 7. Sorting Engine
    sort_by = request.GET.get('sort')
    if sort_by == 'price_low':
        products = products.order_by('price')
    elif sort_by == 'price_high':
        products = products.order_by('-price')
    elif sort_by == 'latest':
        products = products.order_by('-created_date')
    else:
        products = products.order_by('id')

    # Ensure final sets are clean and distinct
    products_distinct = products.distinct()
    product_count = products_distinct.count()

    # 8. Pagination Configuration
    paginator = Paginator(products_distinct, 8)
    page = request.GET.get('page')
    paged_products = paginator.get_page(page)

    context = {
        'products': paged_products,
        'product_count': product_count,
        'categories': categories,
        
        # UI Options lists (Sorted beautifully)
        'ui_colors': sorted(list(ui_colors)),
        'ui_sizes': sorted(list(ui_sizes)),
        
        # Selected tracking states
        'selected_gender': gender_filter or '',
        'selected_min_price': min_price or '',
        'selected_max_price': max_price or '',
        'selected_colors': selected_colors,
        'selected_sizes': selected_sizes,
        'selected_sort': sort_by or '',
    }
    return render(request, 'store/store.html', context)

def product_detail(request, category_slug, product_slug):
    try:
        single_product = Product.objects.get(category__slug=category_slug, slug=product_slug)
        in_cart = CartItem.objects.filter(cart__cart_id=_cart_id(request), product=single_product).exists()
    except Exception as e:
        raise e

    orderproduct = None
    if request.user.is_authenticated:
        orderproduct = OrderProduct.objects.filter(user=request.user, product_id=single_product.id).exists()

    reviews = ReviewRating.objects.filter(product_id=single_product.id, status=True)
    product_gallery = ProductGallery.objects.filter(product_id=single_product.id)

    context = {
        'single_product': single_product,
        'in_cart': in_cart,
        'orderproduct': orderproduct,
        'reviews': reviews,
        'product_gallery': product_gallery,
    }
    return render(request, 'store/product_detail.html', context)

def search(request):
    products = Product.objects.none()
    if 'keyword' in request.GET:
        keyword = request.GET['keyword']
        if keyword:
            products = Product.objects.order_by('-created_date').filter(
                Q(description__icontains=keyword) | Q(product_name__icontains=keyword)
            )

    product_count = products.count()
    context = {
        'products': products,
        'product_count': product_count,
    }
    return render(request, 'store/store.html', context)

def submit_review(request, product_id):
    url = request.META.get('HTTP_REFERER','/store/')
    if request.method == 'POST':
        try:
            reviews = ReviewRating.objects.get(user__id=request.user.id, product__id=product_id)
            form = ReviewForm(request.POST, instance=reviews)
            form.save()
            messages.success(request, 'Thank you! Your review has been updated.')
        except ReviewRating.DoesNotExist:
            form = ReviewForm(request.POST)
            if form.is_valid():
                data = ReviewRating()
                data.subject = form.cleaned_data['subject']
                data.rating = form.cleaned_data['rating']
                data.review = form.cleaned_data['review']
                data.ip = request.META.get('REMOTE_ADDR')
                data.product_id = product_id
                data.user_id = request.user.id
                data.save()
                messages.success(request, 'Thank you! Your review has been submitted.')
        return redirect(url)