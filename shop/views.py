from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login as auth_login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.core.paginator import Paginator
from django.conf import settings
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum
from datetime import timedelta
from django.urls import reverse
from django.core import signing
from datetime import timedelta

from .models import User, Product, Order, Notification, Dispute, DisputeEvidence
from .ai_analyzer import analyze_dispute

import random
import string
import re


# ============================================ #
# HOME PAGE                                    #
# ============================================ #
def home_view(request):
    """Home Page"""
    return render(request, 'shop/home.html')


# ============================================ #
# AUTHENTICATION                               #
# ============================================ #

COOKIE_NAME = 'escrow_accounts'
COOKIE_SALT = 'multi-account-switcher'
def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            # Read existing account list from cookie
            raw = request.COOKIES.get(COOKIE_NAME, '')
            try:
                ids = signing.loads(raw, salt=COOKIE_SALT) if raw else []
                if not isinstance(ids, list):
                    ids = []
            except Exception:
                ids = []
            
            # Add this user if not already there
            if user.id not in ids:
                ids.append(user.id)
            ids = ids[-5:]  # keep last 5
            
            # Log in
            auth_login(request, user)
            
            # Redirect based on role
            if user.is_superuser or user.username == 'admin':
                resp = redirect('admin_dashboard')
            elif user.role == 'seller':
                resp = redirect('seller_dashboard')
            else:
                resp = redirect('buyer_dashboard')
            
            # Save the updated list to the cookie
            signed = signing.dumps(ids, salt=COOKIE_SALT)
            resp.set_cookie(COOKIE_NAME, signed, max_age=30 * 24 * 3600, httponly=True, samesite='Lax')
            return resp
        else:
            return render(request, 'shop/home.html', {
                'error': 'Sorry, your password was incorrect. Please double-check your username and password.',
                'username_value': username,
            })
    
    return render(request, 'shop/home.html')


def switch_account(request):
    """Log out the current user and redirect to login page."""
    from django.contrib.auth import logout as auth_logout
    auth_logout(request)
    return redirect('login')

def switch_to_account(request, user_id):
    """Instantly switch to another already-authenticated account."""
    raw = request.COOKIES.get(COOKIE_NAME, '')
    try:
        ids = signing.loads(raw, salt=COOKIE_SALT) if raw else []
    except Exception:
        ids = []
    
    if user_id not in ids:
        messages.error(request, "You haven't logged into that account yet. Please log in first.")
        return redirect('login')
    
    user = User.objects.filter(id=user_id).first()
    if not user:
        messages.error(request, "Account not found.")
        return redirect('home')
    
    auth_login(request, user)
    messages.success(request, f"Switched to {user.username}")
    
    if user.is_superuser or user.username == 'admin':
        resp = redirect('admin_dashboard')
    elif user.role == 'seller':
        resp = redirect('seller_dashboard')
    else:
        resp = redirect('buyer_dashboard')
    
    # Re-set the cookie (auth_login may have cleared it)
    signed = signing.dumps(ids, salt=COOKIE_SALT)
    resp.set_cookie(COOKIE_NAME, signed, max_age=30 * 24 * 3600, httponly=True, samesite='Lax')
    return resp


def register_view(request):
    if request.user.is_authenticated:
        return redirect('login')
    
    if request.method == 'POST':
        email_or_phone = request.POST.get('email_or_phone')
        password = request.POST.get('password')
        full_name = request.POST.get('full_name')
        username = request.POST.get('username')
        
        if len(password) < 6:
            return render(request, 'shop/register.html', {'error': 'Password must be at least 6 characters'})
        
        if User.objects.filter(username=username).exists():
            return render(request, 'shop/register.html', {'error': 'Username already taken'})
        
        if User.objects.filter(email=email_or_phone).exists():
            return render(request, 'shop/register.html', {'error': 'This email or phone number is already registered'})
        
        user = User.objects.create_user(
            username=username,
            email=email_or_phone,
            password=password,
            first_name=full_name,
            role='buyer'
        )
        user.save()
        
        auth_login(request, user)
        return redirect('buyer_dashboard')
    
    return render(request, 'shop/register.html')


def forgot_password(request):
    if request.method == 'POST':
        identifier = request.POST.get('email', '').strip()
        
        if not identifier:
            return render(request, 'shop/login.html', {
                'error': 'Please enter your username, email, or phone number.'
            })
        
        user = None
        
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if re.match(email_pattern, identifier):
            try:
                user = User.objects.get(email__iexact=identifier)
            except User.DoesNotExist:
                pass
        
        if not user:
            try:
                user = User.objects.get(username__iexact=identifier)
            except User.DoesNotExist:
                pass
        
        if not user:
            try:
                user = User.objects.get(email=identifier)
            except User.DoesNotExist:
                pass
        
        if not user and identifier.isdigit():
            try:
                cleaned_phone = identifier.lstrip('0')
                for u in User.objects.all():
                    if cleaned_phone in u.email or u.email in cleaned_phone:
                        user = u
                        break
            except:
                pass
        
        if not user:
            return render(request, 'shop/login.html', {
                'error': 'No account found with this username, email, or phone number. Please check and try again.'
            })
        
        new_password = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
        user.set_password(new_password)
        user.save()
        
        return render(request, 'shop/login.html', {
            'success': f'✅ Password reset successfully!\nYour new password is: {new_password}\n\nPlease copy this and log in.'
        })
    
    return redirect('login')


def logout_view(request):
    logout(request)
    return redirect('home')


# ============================================ #
# DASHBOARDS                                   #
# ============================================ #
@login_required(login_url='login')
def buyer_dashboard(request):
    """Buyer dashboard - shows buyer's profile and available sellers"""
    seller = None
    try:
        seller = User.objects.get(username='luxe.boutique', role='seller')
    except User.DoesNotExist:
        seller = User.objects.filter(role='seller').first()
    
    context = {
        'user': request.user,
        'profile_user': request.user,          # 👈 who's profile we're showing
        'is_seller_view': False,               # 👈 flag for template
        'seller': seller,
    }
    return render(request, 'shop/buyer_dashboard.html', context)

@login_required(login_url='login')
def seller_view_buyer_dashboard(request, buyer_id):
    """Seller views a specific buyer's dashboard (same layout as the buyer's own)."""
    
    if request.user.role != 'seller':
        messages.error(request, "Only sellers can view buyer dashboards.")
        return redirect('buyer_dashboard')
    
    buyer = get_object_or_404(User, id=buyer_id, role='buyer')
    
    # The seller they're viewing from
    seller = request.user
    
    # Orders this seller placed with THIS buyer
    orders = Order.objects.filter(
        buyer=buyer,
        seller=request.user
    ).order_by('-created_at')
    
    context = {
        'user': request.user,               # still the logged-in seller
        'profile_user': buyer,              # the buyer whose dashboard is being viewed
        'is_seller_view': True,             # 👈 shows "Back to dashboard" banner
        'seller': seller,
        'orders': orders,
    }
    return render(request, 'shop/buyer_dashboard.html', context)


@login_required(login_url='login')
def seller_dashboard(request):
    user = request.user
    products = Product.objects.filter(seller=user).order_by('-created_at')
    orders_count = Order.objects.filter(seller=user).count()
    
    customers = User.objects.filter(
        role='buyer'
    ).exclude(
        is_superuser=True
    ).exclude(
        is_staff=True
    ).exclude(
        username__in=['admin', 'Administrator', 'root']
    ).order_by('-date_joined')
    
    context = {
        'user': user,
        'products': products,
        'customers': customers,
        'orders_count': orders_count,
    }
    return render(request, 'shop/seller_dashboard.html', context)


@login_required(login_url='login')
def admin_dashboard(request):
    if not request.user.is_superuser and request.user.username != 'admin':
        return redirect('login')
    
    total_users = User.objects.exclude(
        username__in=['admin', 'Administrator', 'root']
    ).exclude(
        is_superuser=True
    ).count()
    
    total_sellers = User.objects.filter(role='seller').count()
    total_orders = Order.objects.count()
    pending_orders = Order.objects.filter(admin_notified=False).count()
    
    # ✅ Count pending disputes
    pending_disputes = Dispute.objects.filter(status='PENDING').count()
    
    context = {
        'user': request.user,
        'total_users': total_users,
        'total_sellers': total_sellers,
        'total_orders': total_orders,
        'pending_orders': pending_orders,
        'pending_disputes': pending_disputes,
    }
    return render(request, 'shop/admin_dashboard.html', context)


# ============================================ #
# PRODUCT VIEWS                                #
# ============================================ #
@login_required(login_url='login')
def seller_shop(request):
    try:
        seller = User.objects.get(username='luxe.boutique', role='seller')
    except User.DoesNotExist:
        seller = User.objects.filter(role='seller').first()
    
    products = Product.objects.filter(seller=seller).order_by('-created_at')
    
    context = {
        'seller': seller,
        'products': products,
    }
    return render(request, 'shop/shop.html', context)


@login_required(login_url='login')
def product_detail(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    return render(request, 'shop/product_detail.html', {'product': product})


@login_required(login_url='login')
def add_product(request):
    if request.user.role != 'seller':
        messages.error(request, "You are not authorized to add products.")
        return redirect('buyer_dashboard')
    
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        price = request.POST.get('price')
        original_price = request.POST.get('original_price')
        category = request.POST.get('category')
        image = request.FILES.get('image')
        
        if not all([name, description, price, category]):
            messages.error(request, "Please fill in all required fields.")
            return render(request, 'shop/add_product.html', {'seller': request.user})
        
        product = Product(
            seller=request.user,
            name=name,
            description=description,
            price=price,
            original_price=original_price if original_price else None,
            category=category,
            image=image,
        )
        product.save()
        
        messages.success(request, "✅ Product added successfully!")
        return redirect('seller_dashboard')
    
    return render(request, 'shop/add_product.html', {'seller': request.user})


def load_more_products(request):
    page = request.GET.get('page', 1)
    try:
        seller = User.objects.get(username='luxe.boutique', role='seller')
    except User.DoesNotExist:
        seller = User.objects.filter(role='seller').first()
    
    products = Product.objects.filter(seller=seller).order_by('-created_at')
    paginator = Paginator(products, 9)
    
    try:
        page_obj = paginator.get_page(page)
    except:
        return JsonResponse({'products': [], 'has_next': False})
    
    product_data = []
    for product in page_obj:
        product_data.append({
            'id': product.id,
            'name': product.name,
            'price': str(product.price),
            'original_price': str(product.original_price) if product.original_price else None,
            'discount_percent': product.discount_percent(),
            'image': product.image.url if product.image else None,
        })
    
    return JsonResponse({
        'products': product_data,
        'has_next': page_obj.has_next(),
    })


# ============================================ #
# CHECKOUT & ORDER CONFIRMATION                #
# ============================================ #
@login_required(login_url='login')
def checkout_page(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    
    if request.method == 'POST':
        full_name = request.POST.get('full_name')
        phone = request.POST.get('phone')
        email = request.POST.get('email')
        address = request.POST.get('address')
        city = request.POST.get('city')
        pincode = request.POST.get('pincode')
        size = request.POST.get('size')
        order_notes = request.POST.get('notes', '')
        
        # 👇 Read quantity FIRST, then calculate
        quantity = int(request.POST.get('quantity', 1))
        quantity = max(1, min(quantity, 10))  # clamp 1–10 for safety
        
        # 👇 Multiply by quantity
        product_total = float(product.price) * quantity
        platform_fee = product_total * 0.05
        shipping_charge = 0
        total_amount = product_total + platform_fee + shipping_charge
        
        order = Order.objects.create(
            buyer=request.user,
            seller=product.seller,
            product=product,
            product_name=product.name,
            product_price=product.price,
            platform_fee=platform_fee,
            shipping_charge=shipping_charge,
            total_amount=total_amount,
            full_name=full_name,
            phone=phone,
            email=email,
            address=address,
            city=city,
            pincode=pincode,
            size=size,
            quantity=quantity,
            order_notes=order_notes,
            status='PAID'
        )
        
        Notification.objects.create(
            user=order.seller,
            order=order,
            notification_type='ORDER_PLACED',
            title='📦 New Order Received!',
            message=f'You have a new order #{order.id} for {order.product_name} (x{quantity}) — ₹{order.total_amount}.',
            amount=order.total_amount,
        )
        
        return redirect('order_confirmation', order_id=order.id)
    
    # GET — initial page load (quantity = 1)
    platform_fee = float(product.price) * 0.05
    shipping_charge = 0
    total_amount = float(product.price) + platform_fee + shipping_charge
    
    context = {
        'product': product,
        'platform_fee': platform_fee,
        'shipping_charge': shipping_charge,
        'total_amount': total_amount,
        'user': request.user,
    }
    return render(request, 'shop/checkout.html', context)


@login_required(login_url='login')
def order_confirmation(request, order_id):
    order = get_object_or_404(Order, id=order_id, buyer=request.user)
    return render(request, 'shop/order_confirmation.html', {'order': order})


# ============================================ #
# BUYER TRACKING                               #
# ============================================ #
@login_required(login_url='login')
def track_order(request):
    """Buyer enters tracking ID to track their order"""
    error = None
    
    if request.method == 'POST':
        tracking_id = request.POST.get('tracking_id', '').strip().upper()
        
        if not tracking_id:
            error = "Please enter a tracking ID."
        else:
            try:
                order = Order.objects.get(tracking_number=tracking_id, buyer=request.user)
                return redirect('order_tracking_detail', order_id=order.id)
            except Order.DoesNotExist:
                error = "❌ No order found with this tracking ID. Please check and try again."
    
    recent_orders = Order.objects.filter(buyer=request.user).order_by('-created_at')[:5]
    
    context = {
        'error': error,
        'recent_orders': recent_orders,
    }
    return render(request, 'shop/track_order.html', context)


@login_required(login_url='login')
def buyer_tracking(request):
    """Buyer views all their orders"""
    orders = Order.objects.filter(buyer=request.user).order_by('-created_at')
    return render(request, 'shop/buyer_tracking.html', {'orders': orders})


@login_required(login_url='login')
def order_tracking_detail(request, order_id):
    """Buyer views full tracking details for a specific order"""
    order = get_object_or_404(Order, id=order_id, buyer=request.user)
    
    # Check if a dispute exists for this order
    dispute = Dispute.objects.filter(order=order).order_by('-created_at').first()
    
    context = {
        'order': order,
        'dispute_exists': dispute is not None,
        'dispute': dispute,
    }
    return render(request, 'shop/order_tracking_detail.html', context)


# ============================================ #
# SELLER ORDERS                                #
# ============================================ #
@login_required(login_url='login')
def seller_orders(request):
    """Seller views all orders placed with them"""
    orders = Order.objects.filter(seller=request.user).order_by('-created_at')
    
    pending_count = orders.filter(
        status__in=['PENDING', 'PAID', 'PROCESSING', 'SHIPPED', 'OUT_FOR_DELIVERY']
    ).count()
    
    delivered_count = orders.filter(status='DELIVERED').count()
    
    # ✅ Only count revenue from orders where funds were RELEASED to the seller
    # Refunded orders (fund_status='REFUNDED') are NOT revenue
    # Held orders (fund_status='HELD' or 'RETURN_PENDING') are NOT revenue yet
    total_revenue = orders.filter(
        fund_status='RELEASED'
    ).aggregate(sum=Sum('total_amount'))['sum'] or 0
    
    context = {
        'orders': orders,
        'pending_count': pending_count,
        'delivered_count': delivered_count,
        'total_revenue': total_revenue,
    }
    return render(request, 'shop/seller_orders.html', context)


@login_required(login_url='login')
def update_tracking(request, order_id):
    """Seller updates tracking details for an order"""
    order = get_object_or_404(Order, id=order_id, seller=request.user)
    
    if order.status == 'DELIVERED':
        messages.error(request, "❌ This order has been delivered. Tracking cannot be updated anymore.")
        return redirect('seller_orders')
    
    if order.fund_status in ['RELEASED', 'REFUNDED', 'RETURN_PENDING']:
        messages.error(request, "❌ This order is closed. No further updates allowed.")
        return redirect('seller_orders')
    
    if request.method == 'POST':
        if not order.tracking_company:
            tc = request.POST.get('tracking_company')
            if tc:
                order.tracking_company = tc
        
        if not order.estimated_delivery_days:
            ed = request.POST.get('estimated_delivery_days')
            if ed:
                order.estimated_delivery_days = int(ed)
        
        status = request.POST.get('status')
        # 👇 ONLY CHANGE: Seller cannot set DELIVERED
        allowed = ['PENDING', 'PAID', 'PROCESSING', 'SHIPPED', 'OUT_FOR_DELIVERY']
        
        if status and status in allowed:
            order.status = status
            if status == 'SHIPPED' and not order.shipped_at:
                order.shipped_at = timezone.now()
                if order.estimated_delivery_days:
                    order.estimated_delivery_date = (
                        order.shipped_at.date() + timedelta(days=order.estimated_delivery_days)
                    )
            elif status == 'OUT_FOR_DELIVERY':
                # 👇 Notify buyer to confirm delivery
                order.delivery_confirmation_requested_at = timezone.now()
                Notification.objects.create(
                    user=order.buyer,
                    order=order,
                    notification_type='ORDER_OUT_FOR_DELIVERY',
                    title='🚚 Is Your Order Delivered?',
                    message=(
                        f'Order #{order.id} ({order.product_name}) is out for delivery. '
                        f'Please confirm once you receive it so we can release funds to the seller.'
                    ),
                )
        
        delivery_status = request.POST.get('delivery_status')
        if delivery_status == 'delayed':
            delay_days = request.POST.get('delay_days')
            order.is_delayed = True
            order.delay_days = int(delay_days) if delay_days else 0
            base_date = order.estimated_delivery_date or (order.shipped_at.date() if order.shipped_at else timezone.now().date())
            order.revised_delivery_date = base_date + timedelta(days=order.delay_days)
            
            Notification.objects.create(
                user=order.buyer,
                order=order,
                notification_type='ORDER_DELAYED',
                title='⏰ Delivery Delayed',
                message=f'Order #{order.id} ({order.product_name}) has been delayed by {order.delay_days} day(s). New estimated delivery: {order.revised_delivery_date}.',
            )
        elif delivery_status == 'on_time':
            order.is_delayed = False
            order.delay_days = None
            order.revised_delivery_date = None
        
        order.save()
        messages.success(request, "✅ Order updated successfully!")
        return redirect('seller_orders')
    
    # 👇 ONLY CHANGE: Remove DELIVERED from the choices shown to seller
    seller_status_choices = [
        ('PENDING', 'Pending'),
        ('PAID', 'Paid - Escrow Held'),
        ('PROCESSING', 'Processing'),
        ('SHIPPED', 'Shipped'),
        ('OUT_FOR_DELIVERY', 'Out for Delivery'),
    ]
    
    context = {
        'order': order,
        'status_choices': seller_status_choices,
    }
    return render(request, 'shop/update_tracking.html', context)
# ============================================ #
# SELLER — VIEW BUYER PROFILE                  #
# ============================================ #
@login_required(login_url='login')
def seller_buyer_detail(request, buyer_id):
    """Seller views a specific buyer's profile and order history with them."""
    
    # Only sellers can view this page
    if request.user.role != 'seller':
        messages.error(request, "Only sellers can view buyer profiles.")
        return redirect('buyer_dashboard')
    
    buyer = get_object_or_404(User, id=buyer_id, role='buyer')
    
    # Only show orders this seller placed with THIS buyer
    orders = Order.objects.filter(
        buyer=buyer,
        seller=request.user
    ).order_by('-created_at')
    
    # Compute stats for display
    total_orders = orders.count()
    total_spent = sum(o.total_amount for o in orders if o.fund_status == 'RELEASED')
    
    context = {
        'buyer': buyer,
        'orders': orders,
        'total_orders': total_orders,
        'total_spent': total_spent,
        'user': request.user,
    }
    return render(request, 'shop/seller_buyer_detail.html', context)


# ============================================ #
# ADMIN ORDERS                                 #
# ============================================ #
@login_required(login_url='login')
def admin_orders(request):
    """Admin views all orders"""
    if not request.user.is_superuser and request.user.username != 'admin':
        return redirect('login')
    
    orders = Order.objects.all().order_by('-created_at')
    pending_notifications = orders.filter(admin_notified=False).count()
    orders.filter(admin_notified=False).update(admin_notified=True)
    
    pending_count = orders.filter(status__in=['PENDING', 'PAID', 'PROCESSING']).count()
    delivered_count = orders.filter(status='DELIVERED').count()
    total_revenue = orders.filter(status='DELIVERED').aggregate(sum=Sum('total_amount'))['sum'] or 0
    
    context = {
        'orders': orders,
        'pending_notifications': pending_notifications,
        'pending_count': pending_count,
        'delivered_count': delivered_count,
        'total_revenue': total_revenue,
    }
    return render(request, 'shop/admin_orders.html', context)


# ============================================ #
# ADMIN USER MANAGEMENT                        #
# ============================================ #
@login_required(login_url='login')
def admin_user_list(request):
    """Admin views all users (buyers and sellers)"""
    if not request.user.is_superuser and request.user.username != 'admin':
        return redirect('login')
    
    users = User.objects.exclude(
        username__in=['admin', 'Administrator', 'root']
    ).exclude(
        is_superuser=True
    ).order_by('-date_joined')
    
    buyers = users.filter(role='buyer')
    sellers = users.filter(role='seller')
    
    context = {
        'users': users,
        'buyers': buyers,
        'sellers': sellers,
    }
    return render(request, 'shop/admin_user_list.html', context)


@login_required(login_url='login')
def admin_user_detail(request, user_id):
    """Admin views a specific user's profile"""
    if not request.user.is_superuser and request.user.username != 'admin':
        return redirect('login')
    
    user = get_object_or_404(User, id=user_id)
    orders = Order.objects.filter(buyer=user).order_by('-created_at')[:10]
    products = Product.objects.filter(seller=user).order_by('-created_at')[:10]
    
    context = {
        'profile_user': user,
        'orders': orders,
        'products': products,
    }
    return render(request, 'shop/admin_user_detail.html', context)


# ============================================ #
# ESCROW ENGINE                                #
# ============================================ #
@login_required(login_url='login')
def escrow_dashboard(request):
    """
    Escrow dashboard — ADMIN ONLY.
    Shows held, released, refunded funds + action alerts.
    """
    user = request.user
    
    # ✅ Admin only
    if not (user.is_superuser or user.username == 'admin'):
        messages.error(request, "You don't have access to the escrow platform.")
        return redirect('login')
    
    all_orders = Order.objects.all().order_by('-created_at')
    
    # Categorize
    held_orders = all_orders.filter(fund_status='HELD')
    released_orders = all_orders.filter(fund_status='RELEASED')
    refunded_orders = all_orders.filter(fund_status='REFUNDED')
    
    # Action alerts
    ready_to_release = []
    ready_to_refund = []
    for order in held_orders:
        if order.is_ready_to_release:
            ready_to_release.append(order)
        elif order.is_ready_to_refund:
            ready_to_refund.append(order)
    
    # Financial summary
    total_held = held_orders.aggregate(s=Sum('total_amount'))['s'] or 0
    total_released = released_orders.aggregate(s=Sum('total_amount'))['s'] or 0
    total_refunded = refunded_orders.aggregate(s=Sum('total_amount'))['s'] or 0
    
    context = {
        'role': 'admin',
        'user': user,
        'held_orders': held_orders,
        'released_orders': released_orders,
        'refunded_orders': refunded_orders,
        'total_held': total_held,
        'total_released': total_released,
        'total_refunded': total_refunded,
        'held_count': held_orders.count(),
        'released_count': released_orders.count(),
        'refunded_count': refunded_orders.count(),
        'ready_to_release': ready_to_release,
        'ready_to_refund': ready_to_refund,
        'has_alerts': len(ready_to_release) > 0 or len(ready_to_refund) > 0,
    }
    return render(request, 'shop/escrow_dashboard.html', context)


@login_required(login_url='login')
def escrow_order_detail(request, order_id):
    """Escrow order detail — ADMIN ONLY"""
    user = request.user
    if not (user.is_superuser or user.username == 'admin'):
        return redirect('login')
    
    order = get_object_or_404(Order, id=order_id)
    
    context = {
        'order': order,
        'can_manage': True,
    }
    return render(request, 'shop/escrow_order_detail.html', context)


@login_required(login_url='login')
def escrow_release(request, order_id):
    """Admin manually releases funds to seller"""
    if not (request.user.is_superuser or request.user.username == 'admin'):
        return redirect('login')
    
    order = get_object_or_404(Order, id=order_id)
    
    if order.fund_status == 'HELD':
        order.fund_status = 'RELEASED'
        order.funds_released_at = timezone.now()
        order.escrow_notes = f"Released by admin on {timezone.now().strftime('%b %d, %Y %H:%M')}"
        order.save()
        
        Notification.objects.create(
            user=order.seller,
            order=order,
            notification_type='FUND_RELEASED',
            title='💰 Funds Released!',
            message=f'₹{order.total_amount} for Order #{order.id} ({order.product_name}) has been released to your account.',
            amount=order.total_amount,
        )
        
        messages.success(request, f"✅ Funds released to {order.seller.username}")
    
    return redirect('escrow_order_detail', order_id=order.id)


@login_required(login_url='login')
def escrow_refund(request, order_id):
    """Admin manually refunds buyer"""
    if not (request.user.is_superuser or request.user.username == 'admin'):
        return redirect('login')
    
    order = get_object_or_404(Order, id=order_id)
    
    if order.fund_status == 'HELD':
        order.fund_status = 'REFUNDED'
        order.funds_refunded_at = timezone.now()
        order.escrow_notes = f"Refunded by admin on {timezone.now().strftime('%b %d, %Y %H:%M')}"
        order.save()
        
        Notification.objects.create(
            user=order.buyer,
            order=order,
            notification_type='FUND_REFUNDED',
            title='↩️ Refund Issued!',
            message=f'₹{order.total_amount} for Order #{order.id} ({order.product_name}) has been refunded to your account.',
            amount=order.total_amount,
        )
        
        messages.success(request, f"✅ Funds refunded to {order.buyer.username}")
    
    return redirect('escrow_order_detail', order_id=order.id)


# ============================================ #
# NOTIFICATIONS                                #
# ============================================ #
@login_required(login_url='login')
def get_unread_notifications(request):
    """API endpoint to fetch unread notifications"""
    notifications = Notification.objects.filter(user=request.user, is_read=False)
    data = [
        {
            'id': n.id,
            'type': n.notification_type,
            'title': n.title,
            'message': n.message,
            'amount': str(n.amount) if n.amount else None,
            'created_at': n.created_at.strftime('%b %d, %Y %H:%M'),
        }
        for n in notifications
    ]
    return JsonResponse({'notifications': data})


@login_required(login_url='login')
def mark_notifications_read(request):
    """Mark all notifications as read"""
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return JsonResponse({'status': 'ok'})


# ============================================ #
# AI DISPUTE SYSTEM                            #
# ============================================ #
@login_required(login_url='login')
def raise_dispute(request, order_id):
    """Buyer raises a dispute for a delivered order"""
    order = get_object_or_404(Order, id=order_id, buyer=request.user)
    
    if order.status != 'DELIVERED' or order.fund_status != 'HELD':
        messages.error(request, "Disputes can only be raised for delivered orders with funds still in escrow.")
        return redirect('order_tracking_detail', order_id=order.id)
    
    if order.delivered_at:
        window_end = order.delivered_at + timedelta(hours=24)
        if timezone.now() > window_end:
            messages.error(request, "The 24-hour inspection window has passed.")
            return redirect('order_tracking_detail', order_id=order.id)
    
    existing = Dispute.objects.filter(order=order, status='PENDING').exists()
    if existing:
        messages.error(request, "You have already raised a dispute for this order.")
        return redirect('order_tracking_detail', order_id=order.id)
    
    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip()
        received_image = request.FILES.get('received_image')
        tag_image = request.FILES.get('tag_image')
        
        # 👇 Get selected keywords and multiple evidence files
        keywords_list = request.POST.getlist('issue_keywords')
        selected_keywords = ", ".join(keywords_list)
        evidence_files = request.FILES.getlist('evidence_files')
        
        if not reason:
            messages.error(request, "Please describe the issue.")
            return render(request, 'shop/raise_dispute.html', {'order': order})
        
        dispute = Dispute(
            order=order,
            buyer=request.user,
            reason=reason,
            received_image=received_image,
            tag_image=tag_image,
            selected_keywords=selected_keywords, # 👈 Save keywords
        )
        dispute.save()
        
        # 👇 Save multiple evidence files
        for f in evidence_files:
            DisputeEvidence.objects.create(dispute=dispute, file=f)
        
        # --- AI ANALYSIS ---
        original_path = order.product.image.path if (order.product and order.product.image) else None
        received_path = dispute.received_image.path if dispute.received_image else None
        tag_path = dispute.tag_image.path if dispute.tag_image else None
        
        try:
            from .ai_analyzer import analyze_dispute
            ai_result = analyze_dispute(
                order_image_path=original_path,
                received_image_path=received_path,
                dispute_text=reason,
                ordered_size=order.size,
                tag_image_path=tag_path,
                selected_keywords=selected_keywords # 👈 Pass keywords to AI
            )
            
            dispute.ai_image_score = ai_result['image_score']
            dispute.ai_similarity_percent = ai_result['similarity_percent']
            dispute.ai_text_score = ai_result['text_score']
            dispute.ai_final_score = ai_result['final_score']
            dispute.ai_verdict = ai_result['verdict']
            dispute.ai_matched_keywords = ', '.join(ai_result['matched_keywords'])
            dispute.ai_analyzed_at = timezone.now()
            dispute.ai_size_mismatch = ai_result.get('size_mismatch', False)
            dispute.ai_detected_size_text = ai_result.get('detected_size_text', '')
            debug = ai_result.get('image_debug', {})
            debug_str = " | ".join([f"{k}: {v}" for k, v in debug.items() if v is not None])
            dispute.admin_notes = f"[AI Debug] {debug_str}"
            dispute.save()
        except Exception as e:
            import traceback
            print("\n" + "!" * 70)
            print("AI ANALYSIS CRASHED:")
            print("!" * 70)
            traceback.print_exc()
            print("!" * 70 + "\n")
            
            dispute.ai_verdict = 'REVIEW'
            dispute.ai_analyzed_at = timezone.now()
            dispute.admin_notes = f"AI error: {e}"
            dispute.save()
        
        Notification.objects.create(
            user=order.seller,
            order=order,
            notification_type='ORDER_DISPUTED',
            title='⚠️ Order Disputed by Buyer',
            message=f'The buyer has raised a dispute for Order #{order.id} ({order.product_name}). Reason: {reason}',
        )
        
        messages.success(request, "✅ Dispute submitted. AI analysis complete.")
        return redirect('order_tracking_detail', order_id=order.id)
    
    return render(request, 'shop/raise_dispute.html', {'order': order})


@login_required(login_url='login')
def admin_disputes(request):
    """Admin views all disputes"""
    if not (request.user.is_superuser or request.user.username == 'admin'):
        return redirect('login')
    
    pending_disputes = Dispute.objects.filter(status='PENDING').order_by('-created_at')
    resolved_disputes = Dispute.objects.exclude(status='PENDING').order_by('-reviewed_at')
    
    context = {
        'pending_disputes': pending_disputes,
        'resolved_disputes': resolved_disputes,
        'pending_count': pending_disputes.count(),
        'resolved_count': resolved_disputes.count(),
    }
    return render(request, 'shop/admin_disputes.html', context)


@login_required(login_url='login')
def admin_dispute_detail(request, dispute_id):
    """Admin reviews a specific dispute"""
    if not (request.user.is_superuser or request.user.username == 'admin'):
        return redirect('login')
    
    dispute = get_object_or_404(Dispute, id=dispute_id)
    # 👇 Fetch all uploaded evidence files
    evidences = dispute.evidences.all()
    
    return render(request, 'shop/admin_dispute_detail.html', {
        'dispute': dispute,
        'evidences': evidences
    })


@login_required(login_url='login')
def admin_dispute_decide(request, dispute_id):
    """Admin approves or rejects dispute → triggers refund flow or release"""
    if not (request.user.is_superuser or request.user.username == 'admin'):
        return redirect('login')
    
    if request.method != 'POST':
        return redirect('admin_dispute_detail', dispute_id=dispute_id)
    
    dispute = get_object_or_404(Dispute, id=dispute_id)
    decision = request.POST.get('decision')
    admin_notes = request.POST.get('admin_notes', '').strip()
    
    # Safety: already resolved?
    if dispute.status != 'PENDING':
        messages.error(request, "This dispute has already been resolved.")
        return redirect('admin_dispute_detail', dispute_id=dispute_id)
    
    order = dispute.order
    
    # ============================================ #
    # APPROVE — Start the return flow              #
    # ============================================ #
    if decision == 'approve':
        dispute.status = 'APPROVED'
        order.fund_status = 'RETURN_PENDING'
        order.escrow_notes = (
            f"Dispute approved on {timezone.now().strftime('%b %d, %Y %H:%M')} — "
            f"awaiting buyer to ship item back."
        )
        order.save()
        
        # Notify buyer
        Notification.objects.create(
            user=order.buyer,
            order=order,
            notification_type='DISPUTE_RESOLVED',
            title='📦 Dispute Approved — Ship the Item Back',
            message=(
                f'Your dispute for Order #{order.id} was approved. '
                f'Click here to submit your return tracking number. '
                f'Refund of ₹{order.total_amount} will be processed once the seller confirms receipt.'
            ),
            amount=order.total_amount,
        )
        # Notify seller
        Notification.objects.create(
            user=order.seller,
            order=order,
            notification_type='ORDER_DISPUTED',
            title='⚠️ Dispute Approved — Return Expected',
            message=(
                f'The dispute for Order #{order.id} was approved. '
                f'The buyer will ship the item back to you. '
                f'You will be notified once the return tracking number is submitted.'
            ),
        )
        messages.success(request, "✅ Dispute approved. Awaiting buyer to ship the item back.")
    
    # ============================================ #
    # REJECT — Release funds to seller             #
    # ============================================ #
    elif decision == 'reject':
        dispute.status = 'REJECTED'
        order.fund_status = 'RELEASED'
        order.funds_released_at = timezone.now()
        order.escrow_notes = (
            f"Dispute rejected on {timezone.now().strftime('%b %d, %Y %H:%M')} — "
            f"funds released to seller."
        )
        order.save()
        
        # Notify seller
        Notification.objects.create(
            user=order.seller,
            order=order,
            notification_type='FUND_RELEASED',
            title='💰 Dispute Resolved — Funds Released',
            message=(
                f'The dispute on Order #{order.id} was rejected. '
                f'₹{order.total_amount} has been released to your account.'
            ),
            amount=order.total_amount,
        )
        # Notify buyer
        Notification.objects.create(
            user=order.buyer,
            order=order,
            notification_type='DISPUTE_RESOLVED',
            title='❌ Dispute Rejected',
            message=(
                f'Your dispute for Order #{order.id} was reviewed and rejected. '
                f'Funds have been released to the seller.'
            ),
        )
        messages.success(request, f"Dispute rejected. ₹{order.total_amount} released to seller.")
    
    # ============================================ #
    # INVALID DECISION — Fallback                  #
    # ============================================ #
    else:
        messages.error(request, "Invalid decision. Use 'approve' or 'reject'.")
        return redirect('admin_dispute_detail', dispute_id=dispute_id)
    
    # ============================================ #
    # Save admin review metadata                   #
    # ============================================ #
    dispute.admin_notes = admin_notes
    dispute.reviewed_at = timezone.now()
    dispute.reviewed_by = request.user
    dispute.save()
    
    # ⚠️ CRITICAL: Always return an HttpResponse!
    return redirect('admin_disputes')

# ============================================ #
# RETURN-TO-SELLER FLOW                        #
# ============================================ #
@login_required(login_url='login')
def submit_return_tracking(request, order_id):
    """Buyer submits the return tracking number after dispute approval"""
    order = get_object_or_404(Order, id=order_id, buyer=request.user)
    
    if order.fund_status != 'RETURN_PENDING':
        messages.error(request, "You are not allowed to submit return tracking at this stage.")
        return redirect('order_tracking_detail', order_id=order.id)
    
    if request.method == 'POST':
        carrier = request.POST.get('return_carrier', '').strip()
        tracking = request.POST.get('return_tracking_number', '').strip()
        
        if not carrier or not tracking:
            messages.error(request, "Both carrier and tracking number are required.")
            return render(request, 'shop/submit_return_tracking.html', {'order': order})
        
        order.return_carrier = carrier
        order.return_tracking_number = tracking
        order.return_shipped_at = timezone.now()
        order.return_status = 'INITIATED'
        
        # 👇 Start the 48-hour confirmation countdown for the seller
        order.return_confirmation_deadline = timezone.now() + timedelta(hours=48)
        
        # Auto-generate a courier tracking URL
        order.return_tracking_url = _build_tracking_url(carrier, tracking)
        
        order.save()
        
        # Notify seller with full details + tracking link
        Notification.objects.create(
            user=order.seller,
            order=order,
            notification_type='RETURN_TRACKING_SUBMITTED',
            title='📦 Return Shipped by Buyer — 48h to Confirm',
            message=f'Buyer has shipped the disputed item back. Carrier: {carrier}, Tracking: {tracking}. '
                    f'Please confirm receipt within 48 hours or the escrow platform will auto-refund the buyer.',
        )
        
        messages.success(request, "✅ Return tracking submitted! The seller has 48 hours to confirm receipt.")
        return redirect('order_tracking_detail', order_id=order.id)
    
    return render(request, 'shop/submit_return_tracking.html', {'order': order})


def _build_tracking_url(carrier, tracking_number):
    """Build a courier tracking URL based on the carrier name."""
    carrier_lower = (carrier or '').lower()
    
    # Map common carriers to their tracking URLs
    if 'bluedart' in carrier_lower or 'blue dart' in carrier_lower:
        return f'https://www.bluedart.com/tracking?trackingNumber={tracking_number}'
    elif 'dtdc' in carrier_lower:
        return f'https://www.dtdc.in/tracking/tracking_results.asp?strCnno={tracking_number}'
    elif 'delhivery' in carrier_lower:
        return f'https://www.delhivery.com/track/package/{tracking_number}'
    elif 'india post' in carrier_lower or 'indiapost' in carrier_lower:
        return f'https://www.indiapost.gov.in/_layouts/15/dop.portal.tracking/trackconsignment.aspx'
    elif 'fedex' in carrier_lower:
        return f'https://www.fedex.com/fedextrack/?trknbr={tracking_number}'
    elif 'dhl' in carrier_lower:
        return f'https://www.dhl.com/en/express/tracking.html?AWB={tracking_number}'
    elif 'amazon' in carrier_lower:
        return f'https://track.amazon.in/{tracking_number}'
    elif 'ekart' in carrier_lower:
        return f'https://ekartlogistics.com/shipmenttrack/{tracking_number}'
    elif 'xpressbees' in carrier_lower:
        return f'https://www.xpressbees.com/track/{tracking_number}'
    else:
        # Fallback: a generic Google search
        return f'https://www.google.com/search?q={carrier}+tracking+{tracking_number}'

@login_required(login_url='login')
def seller_confirm_return(request, order_id):
    """Seller confirms they received the returned item -> triggers final refund"""
    order = get_object_or_404(Order, id=order_id, seller=request.user)
    
    # Guard 1: Must be in RETURN_PENDING state
    if order.fund_status != 'RETURN_PENDING':
        messages.error(request, f"❌ This order is not awaiting a return (current: {order.fund_status}).")
        return redirect('seller_orders')
    
    # Guard 2: Buyer must have submitted tracking
    if not order.return_tracking_number:
        messages.error(request, "❌ Buyer has not submitted return tracking yet. Nothing to confirm.")
        return redirect('seller_orders')
    
    # ✅ All checks passed — process the refund
    order.fund_status = 'REFUNDED'
    order.funds_refunded_at = timezone.now()
    order.return_received_at = timezone.now()
    order.return_status = 'RECEIVED'
    order.escrow_notes = (
        f"Return received by seller on {timezone.now().strftime('%b %d, %Y %H:%M')}. "
        f"Funds refunded to buyer."
    )
    order.save()
    
    # Notify buyer — refund is done
    Notification.objects.create(
        user=order.buyer,
        order=order,
        notification_type='FUND_REFUNDED',
        title='💰 Refund Processed!',
        message=f'Seller has confirmed receipt of the returned item. ₹{order.total_amount} has been refunded to your account.',
        amount=order.total_amount,
    )
    
    # Mark dispute as resolved
    dispute = Dispute.objects.filter(order=order).first()
    if dispute:
        dispute.status = 'APPROVED'
        dispute.reviewed_at = timezone.now()
        dispute.save()
    
    messages.success(request, f"✅ Return confirmed. ₹{order.total_amount} refunded to the buyer.")
    return redirect('seller_orders')

# ============================================ #
# ADMIN ESCROW OVERRIDE                        #
# ============================================ #
@login_required(login_url='login')
def admin_force_refund(request, order_id):
    """Admin forces a refund if the seller is unresponsive"""
    if not (request.user.is_superuser or request.user.username == 'admin'):
        return redirect('login')
    
    order = get_object_or_404(Order, id=order_id)
    
    if order.fund_status == 'RETURN_PENDING' and order.return_tracking_number:
        order.fund_status = 'REFUNDED'
        order.funds_refunded_at = timezone.now()
        order.escrow_notes = f"Admin forced refund on {timezone.now().strftime('%b %d, %Y %H:%M')}."
        order.save()
        
        Notification.objects.create(
            user=order.buyer,
            order=order,
            notification_type='FUND_REFUNDED',
            title='💰 Refund Processed by Escrow',
            message=f'The escrow platform has verified your return and refunded ₹{order.total_amount} to your account.',
            amount=order.total_amount,
        )
        messages.success(request, "Force refund issued to buyer.")
    else:
        messages.error(request, "Cannot force refund. Return tracking must be submitted first.")
    
    return redirect('escrow_order_detail', order_id=order.id)

@login_required(login_url='login')
def get_unread_notifications(request):
    """API endpoint to fetch unread notifications with smart redirect URLs"""
    notifications = Notification.objects.filter(user=request.user, is_read=False)
    data = []
    for n in notifications:
        redirect_url = '/'
        if n.order:
            if n.notification_type == 'ORDER_DELIVERED':
                redirect_url = reverse('order_tracking_detail', args=[n.order.id])
            elif n.notification_type == 'ORDER_DELAYED':
                redirect_url = reverse('order_tracking_detail', args=[n.order.id])
            elif n.notification_type == 'DISPUTE_RESOLVED':
                # If funds are RETURN_PENDING and buyer hasn't submitted tracking yet
                if n.order.fund_status == 'RETURN_PENDING' and not n.order.return_tracking_number:
                    redirect_url = reverse('submit_return_tracking', args=[n.order.id])
                else:
                    redirect_url = reverse('order_tracking_detail', args=[n.order.id])
            elif n.notification_type == 'FUND_REFUNDED':
                redirect_url = reverse('order_tracking_detail', args=[n.order.id])
            elif n.notification_type == 'RETURN_TRACKING_SUBMITTED':
                # Seller goes to their orders page to confirm
                redirect_url = reverse('seller_orders')
            elif n.notification_type in ['ORDER_DISPUTED', 'FUND_RELEASED', 'ORDER_PLACED']:
                redirect_url = reverse('seller_orders')
            elif n.notification_type == 'ORDER_OUT_FOR_DELIVERY':
                redirect_url = reverse('order_tracking_detail', args=[n.order.id])
            else:
                redirect_url = reverse('order_tracking_detail', args=[n.order.id])
        
        data.append({
            'id': n.id,
            'type': n.notification_type,
            'title': n.title,
            'message': n.message,
            'amount': str(n.amount) if n.amount else None,
            'created_at': n.created_at.strftime('%b %d, %Y %H:%M'),
            'redirect_url': redirect_url,
        })
    return JsonResponse({'notifications': data})

@login_required(login_url='login')
def update_return_status(request, order_id):
    """Seller updates the return shipment status (In Transit, Out for Delivery, etc.)"""
    order = get_object_or_404(Order, id=order_id, seller=request.user)
    
    if order.fund_status != 'RETURN_PENDING':
        messages.error(request, "This order is not in the return-pending state.")
        return redirect('seller_orders')
    
    if not order.return_tracking_number:
        messages.error(request, "Buyer hasn't submitted return tracking yet.")
        return redirect('seller_orders')
    
    if request.method == 'POST':
        new_status = request.POST.get('return_status')
        valid = ['INITIATED', 'IN_TRANSIT', 'OUT_FOR_DELIVERY']
        
        if new_status not in valid:
            messages.error(request, "Invalid status.")
            return redirect('seller_orders')
        
        order.return_status = new_status
        order.save()
        
        # Notify buyer about progress
        Notification.objects.create(
            user=order.buyer,
            order=order,
            notification_type='RETURN_TRACKING_SUBMITTED',
            title=f'📦 Return Update: {dict(order.RETURN_STATUS_CHOICES).get(new_status, new_status)}',
            message=f'Your return for Order #{order.id} is now: {dict(order.RETURN_STATUS_CHOICES).get(new_status, new_status)}.',
        )
        
        messages.success(request, f"✅ Return status updated to {new_status}.")
        return redirect('seller_orders')
    
    return redirect('seller_orders')

@login_required(login_url='login')
def buyer_update_return_status(request, order_id):
    """Buyer updates the return shipment status (In Transit, Out for Delivery)"""
    order = get_object_or_404(Order, id=order_id, buyer=request.user)
    
    if order.fund_status != 'RETURN_PENDING':
        messages.error(request, "This order is not in the return-pending state.")
        return redirect('order_tracking_detail', order_id=order.id)
    
    if not order.return_tracking_number:
        messages.error(request, "Please submit your return tracking first.")
        return redirect('submit_return_tracking', order_id=order.id)
    
    if request.method == 'POST':
        new_status = request.POST.get('return_status')
        # Buyer can only progress forward (not backwards, cannot set RECEIVED)
        allowed = ['INITIATED', 'IN_TRANSIT', 'OUT_FOR_DELIVERY']
        
        if new_status not in allowed:
            messages.error(request, "Invalid status.")
            return redirect('order_tracking_detail', order_id=order.id)
        
        # Prevent going backwards
        progress_order = ['INITIATED', 'IN_TRANSIT', 'OUT_FOR_DELIVERY']
        current_idx = progress_order.index(order.return_status or 'INITIATED')
        new_idx = progress_order.index(new_status)
        
        if new_idx < current_idx:
            messages.error(request, "You cannot go back to a previous status.")
            return redirect('order_tracking_detail', order_id=order.id)
        
        order.return_status = new_status
        order.save()
        
        # Notify the seller about the progress update
        Notification.objects.create(
            user=order.seller,
            order=order,
            notification_type='RETURN_TRACKING_SUBMITTED',
            title=f'📦 Return Update: {dict(order.RETURN_STATUS_CHOICES).get(new_status, new_status)}',
            message=(
                f'The buyer has updated the return shipment status for Order #{order.id} to '
                f'"{dict(order.RETURN_STATUS_CHOICES).get(new_status, new_status)}". '
                f'Please confirm receipt once the package arrives.'
            ),
        )
        
        messages.success(request, f"✅ Return status updated to {dict(order.RETURN_STATUS_CHOICES).get(new_status, new_status)}.")
        return redirect('order_tracking_detail', order_id=order.id)
    
    return redirect('order_tracking_detail', order_id=order.id)

@login_required(login_url='login')
def buyer_confirm_delivery(request, order_id):
    """Buyer confirms whether they received the order"""
    order = get_object_or_404(Order, id=order_id, buyer=request.user)
    
    if order.status != 'OUT_FOR_DELIVERY':
        messages.error(request, "This action is only available when the order is out for delivery.")
        return redirect('order_tracking_detail', order_id=order.id)
    
    if request.method == 'POST':
        response = request.POST.get('response')
        
        if response == 'delivered':
            # ✅ Buyer confirms — finalize delivery
            order.status = 'DELIVERED'
            order.delivered_at = timezone.now()
            order.buyer_delivery_response_at = timezone.now()
            order.save()
            
            # Notify seller — tracking is now locked
            Notification.objects.create(
                user=order.seller,
                order=order,
                notification_type='ORDER_DELIVERED',
                title='✅ Buyer Confirmed Delivery',
                message=(
                    f'Buyer confirmed receiving Order #{order.id} ({order.product_name}). '
                    f'Your order tracking is now locked. Funds will be released after the 24-hour inspection window.'
                ),
            )
            
            messages.success(request, "✅ Delivery confirmed! Your 24-hour inspection window has started. Raise a dispute if anything is wrong.")
        
        elif response == 'not_delivered':
            # ❌ Buyer says not received — notify seller
            order.buyer_delivery_response_at = timezone.now()
            order.save()
            
            Notification.objects.create(
                user=order.seller,
                order=order,
                notification_type='ORDER_DELAYED',
                title='⚠️ Buyer Has Not Received the Order',
                message=(
                    f'Buyer reported NOT receiving Order #{order.id}. '
                    f'Please check with the courier and update the tracking status or mark as delayed.'
                ),
            )
            
            messages.warning(request, "We've notified the seller. They will investigate and update you soon.")
        
        return redirect('order_tracking_detail', order_id=order.id)
    
    return redirect('order_tracking_detail', order_id=order.id)

def logout_current_only(request):
    """Log out current user but keep others switchable."""
    raw = request.COOKIES.get(COOKIE_NAME, '')
    try:
        ids = signing.loads(raw, salt=COOKIE_SALT) if raw else []
    except Exception:
        ids = []
    
    current_id = request.user.id if request.user.is_authenticated else None
    ids = [uid for uid in ids if uid != current_id]
    
    if ids:
        # Switch to the next available account
        next_user = User.objects.filter(id=ids[-1]).first()
        if next_user:
            auth_login(request, next_user)
            resp = redirect('admin_dashboard' if next_user.is_superuser else (
                'seller_dashboard' if next_user.role == 'seller' else 'buyer_dashboard'
            ))
            signed = signing.dumps(ids, salt=COOKIE_SALT)
            resp.set_cookie(COOKIE_NAME, signed, max_age=30 * 24 * 3600, httponly=True, samesite='Lax')
            return resp
    
    # No other accounts — full logout
    logout(request)
    resp = redirect('home')
    resp.delete_cookie(COOKIE_NAME)
    return resp


def logout_view(request):
    """Full logout — clears everything."""
    logout(request)
    resp = redirect('home')
    resp.delete_cookie(COOKIE_NAME)
    return resp

@login_required(login_url='login')
def all_notifications(request):
    """Full page listing all notifications for the current user."""
    notifs = Notification.objects.filter(user=request.user).order_by('-created_at')
    
    # Mark all as read when viewing this page
    unread = notifs.filter(is_read=False)
    unread_count = unread.count()
    unread.update(is_read=True)
    
    context = {
        'notifications': notifs,
        'unread_count': unread_count,
        'total_count': notifs.count(),
    }
    return render(request, 'shop/all_notifications.html', context)

@login_required(login_url='login')
def buyer_confirm_product_ok(request, order_id):
    """
    Buyer confirms the product is fine → release escrow to seller immediately,
    skipping the 24-hour auto-release window.
    """
    order = get_object_or_404(Order, id=order_id, buyer=request.user)
    
    # Guard 1: Order must be DELIVERED
    if order.status != 'DELIVERED':
        messages.error(request, "You can only confirm products that have been delivered.")
        return redirect('order_tracking_detail', order_id=order.id)
    
    # Guard 2: Funds must still be held
    if order.fund_status != 'HELD':
        messages.error(request, f"This order's funds are already {order.fund_status.lower()}.")
        return redirect('order_tracking_detail', order_id=order.id)
    
    # Guard 3: No active pending dispute
    pending_dispute = Dispute.objects.filter(order=order, status='PENDING').first()
    if pending_dispute:
        messages.error(request, "You can't confirm the product while a dispute is under review.")
        return redirect('order_tracking_detail', order_id=order.id)
    
    # ✅ All checks passed — release funds to seller
    order.fund_status = 'RELEASED'
    order.funds_released_at = timezone.now()
    order.escrow_notes = (
        f"Buyer confirmed product on {timezone.now().strftime('%b %d, %Y %H:%M')} — "
        f"funds released to seller immediately (skipped 24h window)."
    )
    order.save()
    
    # Notify seller — money is in!
    Notification.objects.create(
        user=order.seller,
        order=order,
        notification_type='FUND_RELEASED',
        title='💰 Payment Released!',
        message=(
            f'Buyer confirmed receiving Order #{order.id} ({order.product_name}). '
            f'₹{order.total_amount} has been released to your account.'
        ),
        amount=order.total_amount,
    )
    
    # Optional: also notify buyer for their own record
    Notification.objects.create(
        user=order.buyer,
        order=order,
        notification_type='FUND_RELEASED',
        title='✅ Product Confirmed',
        message=(
            f'Thank you for confirming Order #{order.id}. '
            f'₹{order.total_amount} has been released to the seller.'
        ),
    )
    
    messages.success(
        request,
        f"✅ Product confirmed! ₹{order.total_amount} has been released to the seller."
    )
    return redirect('order_tracking_detail', order_id=order.id)