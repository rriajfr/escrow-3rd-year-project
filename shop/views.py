from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login as auth_login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.core.paginator import Paginator
from django.conf import settings
from .models import User, Product
import random
import string
import re
from django.contrib import messages

def home_view(request):
    """Home Page"""
    return render(request, 'shop/home.html')

def login_view(request):
    if request.user.is_authenticated:
        # ✅ CHECK ADMIN FIRST
        if request.user.is_superuser or request.user.username == 'admin':
            return redirect('admin_dashboard')
        elif request.user.role == 'seller':
            return redirect('seller_dashboard')
        else:
            return redirect('buyer_dashboard')
        
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            auth_login(request, user)
            # ✅ CHECK ADMIN FIRST HERE TOO
            if user.is_superuser or user.username == 'admin':
                return redirect('admin_dashboard')
            elif user.role == 'seller':
                return redirect('seller_dashboard')
            else:
                return redirect('buyer_dashboard')
        else:
            return render(request, 'shop/login.html', {'error': 'Invalid username or password'})
    return render(request, 'shop/login.html')

def register_view(request):
    if request.user.is_authenticated:
        return redirect('login')
    
    if request.method == 'POST':
        email_or_phone = request.POST.get('email_or_phone')
        password = request.POST.get('password')
        full_name = request.POST.get('full_name')
        username = request.POST.get('username')
        
        # Validate password length
        if len(password) < 6:
            return render(request, 'shop/register.html', {'error': 'Password must be at least 6 characters'})
        
        # Validate username
        if User.objects.filter(username=username).exists():
            return render(request, 'shop/register.html', {'error': 'Username already taken'})
        
        # Check if email/phone already exists
        if User.objects.filter(email=email_or_phone).exists():
            return render(request, 'shop/register.html', {'error': 'This email or phone number is already registered'})
        
        # Create user
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
        
        # 1. Check if it's a valid email format
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if re.match(email_pattern, identifier):
            try:
                user = User.objects.get(email__iexact=identifier)
            except User.DoesNotExist:
                pass
        
        # 2. Check if it's a username
        if not user:
            try:
                user = User.objects.get(username__iexact=identifier)
            except User.DoesNotExist:
                pass
        
        # 3. Check if it's a phone number (stored in email field)
        if not user:
            try:
                user = User.objects.get(email=identifier)
            except User.DoesNotExist:
                pass
        
        # 4. Check if it's a phone number with variations
        if not user and identifier.isdigit():
            try:
                cleaned_phone = identifier.lstrip('0')
                # Try to find user with this phone number anywhere in email field
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
        
        # Generate a random password
        new_password = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
        user.set_password(new_password)
        user.save()
        
        return render(request, 'shop/login.html', {
            'success': f'✅ Password reset successfully!\nYour new password is: {new_password}\n\nPlease copy this and log in.'
        })
    
    return redirect('login')

def logout_view(request):
    logout(request)
    return redirect('login')

@login_required(login_url='login')
def buyer_dashboard(request):
    try:
        seller = User.objects.get(username='luxe.boutique', role='seller')
    except User.DoesNotExist:
        seller = None
    
    context = {
        'user': request.user,
        'seller': seller,
    }
    return render(request, 'shop/buyer_dashboard.html', context)

@login_required(login_url='login')
def seller_dashboard(request):
    user = request.user
    products = Product.objects.filter(seller=user).order_by('-created_at')
    
    # Get ALL buyers EXCEPT admin/superusers
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
    }
    return render(request, 'shop/seller_dashboard.html', context)

@login_required(login_url='login')
def admin_dashboard(request):
    # Only allow admin users
    if not request.user.is_superuser and request.user.username != 'admin':
        return redirect('login')
    
    # Count users - EXCLUDING ADMIN
    total_users = User.objects.exclude(
        username__in=['admin', 'Administrator', 'root']
    ).exclude(
        is_superuser=True
    ).count()
    
    total_sellers = User.objects.filter(
        role='seller'
    ).exclude(
        username__in=['admin', 'Administrator', 'root']
    ).exclude(
        is_superuser=True
    ).count()
    
    total_buyers = User.objects.filter(
        role='buyer'
    ).exclude(
        username__in=['admin', 'Administrator', 'root']
    ).exclude(
        is_superuser=True
    ).count()
    
    total_orders = 0  # Add when you create Order model
    pending_disputes = 0  # Add when you create Dispute model
    
    # Recent users (last 5) - EXCLUDING ADMIN
    recent_users = User.objects.exclude(
        username__in=['admin', 'Administrator', 'root']
    ).exclude(
        is_superuser=True
    ).order_by('-date_joined')[:5]
    
    # Recent orders (placeholder - add when Order model exists)
    recent_orders = []
    
    context = {
        'user': request.user,
        'total_users': total_users,
        'total_sellers': total_sellers,
        'total_buyers': total_buyers,
        'total_orders': total_orders,
        'pending_disputes': pending_disputes,
        'recent_users': recent_users,
        'recent_orders': recent_orders,
    }
    return render(request, 'shop/admin_dashboard.html', context)

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

# def checkout_placeholder(request, product_id):
#     return HttpResponse(f"""
#     <h1>🛒 Escrow Checkout Page</h1>
#     <p><strong>Product ID:</strong> {product_id}</p>
#     <p><em>This page will automatically fetch product details and show the Escrow Payment screen.</em></p>
#     <br>
#     <a href="/shop/">⬅ Go back to Shop</a>
#     """)

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


@login_required(login_url='login')
def checkout_page(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    
    # Platform fee (5% of product price)
    platform_fee = float(product.price) * 0.05
    shipping_charge = 0  # Free shipping
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
def add_product(request):
    # Only sellers can add products
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
        
        # Basic validation
        if not all([name, description, price, category]):
            messages.error(request, "Please fill in all required fields.")
            return render(request, 'shop/add_product.html', {'seller': request.user})
        
        # Create product
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