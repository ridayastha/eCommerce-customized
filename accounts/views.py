from django.shortcuts import render, redirect
from django.urls import reverse
from .forms import RegistrationForm, UserForm, UserProfileForm
from .models import Account, UserProfile
from orders.models import Order, OrderProduct
from django.contrib import messages, auth
from django.contrib.auth.decorators import login_required
from django.contrib.sites.shortcuts import get_current_site
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMessage
from carts.views import _cart_id
from carts.models import Cart, CartItem


def register(request):
    if request.user.is_authenticated:
        next_url = request.POST.get('next', request.GET.get('next', 'dashboard'))
        return redirect(next_url)
    
    next_destination = request.POST.get('next', request.GET.get('next', ''))

    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            first_name = form.cleaned_data['first_name']
            last_name = form.cleaned_data['last_name']
            phone_number = form.cleaned_data['phone_number']
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            username = email.split("@")[0]

            # User is created with is_active=False (ensure this is in your models.py)
            user = Account.objects.create_user(
                first_name=first_name,
                last_name=last_name,
                email=email,
                username=username,
                password=password,
            )
            user.phone_number = phone_number
            user.save()

            # USER ACTIVATION EMAIL
            current_site = get_current_site(request)
            mail_subject = 'Please activate your account'
            message = render_to_string('accounts/account_verification_email.html', {
                'user': user,
                'domain': current_site.domain,
                'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                'token': default_token_generator.make_token(user),
            })
            send_email = EmailMessage(mail_subject, message, to=[email])
            try:
                send_email.send()
                messages.success(request,f'Registration successful. Please check your email ({email}) to activate your account.')
            except Exception:
                messages.error(request, 'Account created, but we failed to send the activation email. Please contact support.')
            if next_destination:
                return redirect(f"{reverse('login')}?next={next_destination}")
            return redirect('login')
    else:
        form = RegistrationForm()
    return render(request, 'accounts/register.html', {'form': form})


def login(request):
    # 1. Prevent logged-in users from seeing the login page again
    if request.user.is_authenticated:
        next_url = request.POST.get('next', request.GET.get('next', 'dashboard'))
        return redirect(next_url)

    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')

        # 2. Authenticate the user
        user = auth.authenticate(email=email, password=password)

        if user is not None:
            # 3. SECURITY GATE: Only allow active (verified) users
            if user.is_active:

                # --- START CART MERGING LOGIC ---
                try:
                    # Get the guest cart from the session
                    cart = Cart.objects.get(cart_id=_cart_id(request))
                    guest_cart_items = CartItem.objects.filter(cart=cart)

                    if guest_cart_items.exists():
                        # Get all existing cart items for this user to check for duplicates
                        user_cart_items = CartItem.objects.filter(user=user)

                        # Create a list of existing variations for items already in the user's cart
                        # This helps us decide: "Should I update quantity OR create a new row?"
                        ex_var_list = []
                        id_list = []
                        for item in user_cart_items:
                            ex_var_list.append(list(item.variations.all()))
                            id_list.append(item.id)

                        for item in guest_cart_items:
                            current_item_vars = list(item.variations.all())

                            # If this specific product with these variations is already in the user's cart
                            if current_item_vars in ex_var_list:
                                # Find the index to get the correct CartItem ID
                                index = ex_var_list.index(current_item_vars)
                                item_id = id_list[index]

                                # Update the quantity of the existing user item
                                user_item = CartItem.objects.get(id=item_id)
                                user_item.quantity += item.quantity
                                user_item.user = user
                                user_item.save()
                                item.delete()  # Remove the guest item since it's now merged
                            else:
                                # This is a new product/variation combo for the user
                                item.user = user
                                item.save()

                except Cart.DoesNotExist:
                    pass  # No guest cart exists, just proceed to login
                # --- END CART MERGING LOGIC ---

                # 4. Finalize login
                auth.login(request, user)
                messages.success(request, 'You are now logged in.')

                # Handle 'next' parameter (useful for redirected checkouts)
                next_url = request.POST.get('next', request.GET.get('next', 'dashboard'))
                return redirect(next_url)

            else:
                # 5. Handle unverified users
                messages.error(request,
                               'Your account is not activated. Please check your email for the activation link.')
                return redirect('login')
        else:
            # 6. Handle invalid credentials
            messages.error(request, 'Invalid email or password.')
            return redirect('login')

    return render(request, 'accounts/login.html')

@login_required(login_url='login')
def logout(request):
    list(messages.get_messages(request))
    auth.logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('login')

def activate(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = Account.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, Account.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        UserProfile.objects.get_or_create(user=user)
        messages.success(request, 'Congratulations! Your account is activated.')
        return redirect('login')
    else:
        messages.error(request, 'Invalid activation link')
        return redirect('register')

@login_required(login_url='login')
def dashboard(request):
    orders = Order.objects.order_by('created_at').filter(user_id=request.user.id, is_ordered=True)
    orders_count = orders.count()

    userprofile = UserProfile.objects.filter(user=request.user).first()  # Use first() to handle missing profiles

    context = {
      'orders_count': orders_count,
      'userprofile': userprofile,
    }
    return render(request, 'accounts/dashboard.html', context)


def forgotPassword(request):
    # REFINEMENT: Don't let logged-in users reset password this way
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        email = request.POST['email']
        if Account.objects.filter(email=email).exists():
            user = Account.objects.get(email=email)

            current_site = get_current_site(request)
            mail_subject = 'Reset Your Password'
            message = render_to_string('accounts/reset_password_email.html', {
                'user': user,
                'domain': current_site.domain,
                'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                'token': default_token_generator.make_token(user),
            })

            send_email = EmailMessage(mail_subject, message, to=[email])

            # REFINEMENT: Email crash protection
            try:
                send_email.send()
                messages.success(request, 'Password reset email has been sent to your email address.')
            except Exception:
                messages.error(request, "Failed to send reset email. Please try again later.")

            return redirect('login')
        else:
            messages.error(request, 'Account does not exist!')
            return redirect('forgotPassword')
    return render(request, 'accounts/forgotPassword.html')

def resetpassword_validate(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = Account.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, Account.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        request.session['uid'] = uid
        messages.success(request, 'Please reset your password')
        return redirect('resetPassword')
    else:
        messages.error(request, 'This link has expired!')
        return redirect('login')

def resetPassword(request):
    if request.method == 'POST':
        password = request.POST['password']
        confirm_password = request.POST['confirm_password']

        if password == confirm_password:
            uid = request.session.get('uid')
            if uid:
                try:
                    user = Account.objects.get(pk=uid)
                    user.set_password(password)
                    user.save()
                    # REFINEMENT: Clear the session key safely
                    request.session.pop('uid', None)
                    messages.success(request, 'Password reset successful')
                    return redirect('login')
                except Account.DoesNotExist:
                    messages.error(request, 'User not found.')
                    return redirect('forgotPassword')
            else:
                messages.error(request, 'Session expired. Please start the process again.')
                return redirect('forgotPassword')
        else:
            messages.error(request, 'Passwords do not match')
            return redirect('resetPassword')
    else:
        # REFINEMENT: Block direct access to this URL if session uid is missing
        if not request.session.get('uid'):
            return redirect('login')
        return render(request, 'accounts/resetPassword.html')

@login_required(login_url='login')
def my_orders(request):
    orders = Order.objects.filter(user=request.user, is_ordered=True).order_by('-created_at')
    context = {
       'orders': orders,
    }
    return render(request, 'accounts/my_orders.html', context)

# @login_required(login_url='login')
# def edit_profile(request):
#     userprofile = get_object_or_404(UserProfile, user=request.user)

#     if request.method == 'POST':
#         user_form = UserForm(request.POST, instance=request.user)
#         profile_form = UserProfileForm(request.POST, request.FILES, instance=userprofile)

#         # Ensure both forms are valid before accessing cleaned_data
#         if user_form.is_valid() and profile_form.is_valid():
#             # Check if the profile picture should be cleared
#             if profile_form.cleaned_data.get('clear_profile_picture'):
#                 userprofile.profile_picture = None  # Clear profile picture
#                 userprofile.save()

#             # Save the forms
#             user_form.save()
#             profile_form.save()

#             messages.success(request, 'Your profile has been updated.')
#             return redirect('edit_profile')

#     else:
#         user_form = UserForm(instance=request.user)
#         profile_form = UserProfileForm(instance=userprofile)

#     context = {
#         'user_form': user_form,
#         'profile_form': profile_form,
#         'userprofile': userprofile,
#     }

#     return render(request, 'accounts/edit_profile.html', context)

@login_required(login_url='login')
def edit_profile(request):
    # Try to get the user's profile or create it if it doesn't exist
    userprofile, created = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        user_form = UserForm(request.POST, instance=request.user)
        profile_form = UserProfileForm(request.POST, request.FILES, instance=userprofile)

        # Ensure both forms are valid before accessing cleaned_data
        if user_form.is_valid() and profile_form.is_valid():
            # Check if the profile picture should be cleared
            if profile_form.cleaned_data.get('clear_profile_picture'):
                userprofile.profile_picture = None  # Clear profile picture
                userprofile.save()

            # Save the forms
            user_form.save()
            profile_form.save()

            messages.success(request, 'Your profile has been updated.')
            return redirect('edit_profile')

    else:
        user_form = UserForm(instance=request.user)
        profile_form = UserProfileForm(instance=userprofile)

    context = {
        'user_form': user_form,
        'profile_form': profile_form,
        'userprofile': userprofile,
    }

    return render(request, 'accounts/edit_profile.html', context)



@login_required(login_url='login')
def change_password(request):
    if request.method == 'POST':
        current_password = request.POST['current_password']
        new_password = request.POST['new_password']
        confirm_password = request.POST['confirm_password']

        user = Account.objects.get(username__exact=request.user.username)

        if new_password == confirm_password:
            success = user.check_password(current_password)
            if success:
                user.set_password(new_password)
                user.save()
                messages.success(request, 'Password updated successfully.')
                return redirect('change_password')
            else:
                messages.error(request, 'Please enter a valid current password')
                return redirect('change_password')
        else:
            messages.error(request, 'Passwords do not match!')
            return redirect('change_password')
    return render(request, 'accounts/change_password.html')

@login_required(login_url='login')
def order_detail(request, order_id):
    order_detail = OrderProduct.objects.filter(order__order_number=order_id)
    order = Order.objects.get(order_number=order_id)
    subtotal = 0
    for i in order_detail:
        subtotal += i.product_price * i.quantity

    context = {
      'order_detail': order_detail,
      'order': order,
      'subtotal': subtotal,
    }
    return render(request, 'accounts/order_detail.html', context)
