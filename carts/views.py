from django.shortcuts import render, redirect, get_object_or_404
from store.models import Product, Variation
from .models import Cart, CartItem, Enquiry
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.conf import settings
from django.contrib import messages
from decimal import Decimal
import random


# Helper function to handle session-based guest carts
def _cart_id(request):
    cart = request.session.session_key
    if not cart:
        cart = request.session.create()
    return cart


# DRY Helper Function: Calculates and returns all cart computations dynamically
def _get_cart_data(request):
    total = 0
    quantity = 0
    cart_items = None
    tax = 0
    grand_total = 0
    
    try:
        if request.user.is_authenticated:
            cart_items = CartItem.objects.filter(user=request.user, is_active=True)
        else:
            try:
                cart = Cart.objects.get(cart_id=_cart_id(request))
                cart_items = CartItem.objects.filter(cart=cart, is_active=True)
            except Cart.DoesNotExist:
                cart_items = None

        if cart_items:
            for cart_item in cart_items:
                total += (cart_item.product.price * cart_item.quantity)
                quantity += cart_item.quantity
            tax = (2 * total) / 100  # 2% Tax calculation
            grand_total = total + tax
    except ObjectDoesNotExist:
        pass

    return {
        'total': total,
        'quantity': quantity,
        'cart_items': cart_items,
        'tax': tax,
        'grand_total': grand_total,
    }


def add_cart(request, product_id):
    current_user = request.user
    product = Product.objects.get(id=product_id)
    product_variation = []
    
    if request.method == 'POST':
        for item in request.POST:
            key = item
            value = request.POST[key]
            try:
                variation = Variation.objects.get(
                    product=product,
                    variation_category__iexact=key,
                    variation_value__iexact=value
                )
                product_variation.append(variation)
            except Variation.DoesNotExist:
                pass

    if current_user.is_authenticated:
        cart_items = CartItem.objects.filter(product=product, user=current_user)
        ex_var_list = [list(item.variations.all()) for item in cart_items]
        id_list = [item.id for item in cart_items]

        if product_variation in ex_var_list:
            index = ex_var_list.index(product_variation)
            item_id = id_list[index]
            item = CartItem.objects.get(id=item_id)
            item.quantity += 1
            item.save()
        else:
            cart_item = CartItem.objects.create(product=product, quantity=1, user=current_user)
            if product_variation:
                cart_item.variations.add(*product_variation)
            cart_item.save()
    else:
        try:
            cart = Cart.objects.get(cart_id=_cart_id(request))
        except Cart.DoesNotExist:
            cart = Cart.objects.create(cart_id=_cart_id(request))
        cart.save()

        cart_items = CartItem.objects.filter(product=product, cart=cart)
        ex_var_list = [list(item.variations.all()) for item in cart_items]
        id_list = [item.id for item in cart_items]

        if product_variation in ex_var_list:
            index = ex_var_list.index(product_variation)
            item_id = id_list[index]
            item = CartItem.objects.get(id=item_id)
            item.quantity += 1
            item.save()
        else:
            cart_item = CartItem.objects.create(product=product, quantity=1, cart=cart)
            if product_variation:
                cart_item.variations.add(*product_variation)
            cart_item.save()

    return redirect('cart')


def remove_cart(request, product_id, cart_item_id):
    product = get_object_or_404(Product, id=product_id)
    try:
        if request.user.is_authenticated:
            cart_item = CartItem.objects.get(product=product, user=request.user, id=cart_item_id)
        else:
            cart = Cart.objects.get(cart_id=_cart_id(request))
            cart_item = CartItem.objects.get(product=product, cart=cart, id=cart_item_id)
        
        if cart_item.quantity > 1:
            cart_item.quantity -= 1
            cart_item.save()
        else:
            cart_item.delete()
    except CartItem.DoesNotExist:
        pass
    return redirect('cart')


def remove_cart_item(request, product_id, cart_item_id):
    product = get_object_or_404(Product, id=product_id)
    try:
        if request.user.is_authenticated:
            cart_item = CartItem.objects.get(product=product, user=request.user, id=cart_item_id)
        else:
            cart = Cart.objects.get(cart_id=_cart_id(request))
            cart_item = CartItem.objects.get(product=product, cart=cart, id=cart_item_id)
        cart_item.delete()
    except CartItem.DoesNotExist:
        pass
    return redirect('cart')


def cart(request):
    context = _get_cart_data(request)
    return render(request, 'store/cart.html', context)


@login_required(login_url='login')
def checkout(request):
    context = _get_cart_data(request)
    return render(request, 'store/checkout.html', context)



def enquiry_view(request):
    context = _get_cart_data(request)

    if request.method == 'POST':
        # Provide string fallbacks to prevent NULL type conflicts
        name = request.POST.get('name', '') or ''
        phone_number = request.POST.get('phone_number', '') or ''
        message = request.POST.get('message', '') or ''
        
        # Safe Email Fallback
        if request.user.is_authenticated:
            email = getattr(request.user, 'email', '') or ''
        else:
            email = request.POST.get('email', '') or ''

        enquiry_id = str(random.randint(100000, 999999))

        # Snapshot cart content strings
        cart_details = ""
        static_cart_list = []
        
        if context['cart_items']:
            for item in context['cart_items']:
                variations = ", ".join([v.variation_value for v in item.variations.all()])
                var_str = f" ({variations})" if variations else ""
                
                cart_details += f"- {item.product.product_name}{var_str} x {item.quantity}\n"
                
                static_cart_list.append({
                    'product_name': item.product.product_name,
                    'price': item.product.price,
                    'quantity': item.quantity,
                    'variations': variations
                })
        else:
            cart_details = "No items in cart.\n"

        # Safe Money Float-to-Decimal conversion for strict PostgreSQL tables
        safe_grand_total = Decimal(str(context['grand_total']))

        # Save the enquiry safely to the database    
        Enquiry.objects.create(
            user=request.user if request.user.is_authenticated else None,
            enquiry_id=enquiry_id,
            name=name,
            email=email,
            phone_number=phone_number,
            message=message,
            cart_details=cart_details,
            grand_total=safe_grand_total # Wrapped Decimal value
        )

        success_context = {
            'name': name,
            'email': email,
            'phone_number': phone_number,
            'message': message,
            'enquiry_id': enquiry_id,
            'cart_items': static_cart_list, 
            'total': context['total'],
            'tax': context['tax'],
            'grand_total': context['grand_total'],
        }

        # --- Email Admin Notification ---
        admin_subject = f"New Store Enquiry #{enquiry_id} from {name}"
        admin_body = f"Customer: {name}\nEmail: {email}\nPhone: {phone_number}\n\nItems:\n{cart_details}\nTotal: ${context['grand_total']}\n\nMessage:\n{message}"

        try:
            send_mail(
                subject=admin_subject,
                message=admin_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=['ridaya350@gmail.com'], 
                fail_silently=True,
            )
        except Exception:
            pass 

        # Clear active cart objects after recording it in the database
        if context['cart_items']:
            context['cart_items'].delete()

        return render(request, 'orders/enquiry_success.html', success_context)

    return render(request, 'store/enquiry_form.html', context)