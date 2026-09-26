from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from datetime import timedelta


# ============================================ #
# USER MODEL                                   #
# ============================================ #
class User(AbstractUser):
    ROLE_CHOICES = (
        ('buyer', 'Buyer'),
        ('seller', 'Seller'),
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='buyer')
    
    profile_picture = models.ImageField(upload_to='profiles/', blank=True, null=True)
    bio = models.TextField(blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    business_category = models.CharField(max_length=100, blank=True, null=True)
    location = models.CharField(max_length=200, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    
    def __str__(self):
        return self.username


# ============================================ #
# PRODUCT MODEL                                #
# ============================================ #
class Product(models.Model):
    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=200)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    original_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    category = models.CharField(max_length=50, default='Clothing')
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def discount_percent(self):
        if self.original_price and self.original_price > self.price:
            return int(((self.original_price - self.price) / self.original_price) * 100)
        return 0

    def __str__(self):
        return self.name


# ============================================ #
# ORDER MODEL                                  #
# ============================================ #
class Order(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PAID', 'Paid - Escrow Held'),
        ('PROCESSING', 'Processing'),
        ('SHIPPED', 'Shipped'),
        ('OUT_FOR_DELIVERY', 'Out for Delivery'),
        ('DELIVERED', 'Delivered'),
        ('COMPLETED', 'Completed'),
        ('REFUNDED', 'Refunded'),
        ('DISPUTED', 'Disputed'),
    ]
    
    # 👇 UPDATED: Added RETURN_PENDING
    FUND_STATUS_CHOICES = [
        ('HELD', 'Held in Escrow'),
        ('RETURN_PENDING', 'Return Pending'),
        ('RELEASED', 'Released to Seller'),
        ('REFUNDED', 'Refunded to Buyer'),
    ]

    # --- Relationships ---
    buyer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='seller_orders')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    
    # --- Product snapshot ---
    product_name = models.CharField(max_length=200)
    product_price = models.DecimalField(max_digits=10, decimal_places=2)
    platform_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    shipping_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    # --- Customer details ---
    full_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    email = models.EmailField()
    address = models.TextField()
    city = models.CharField(max_length=50)
    pincode = models.CharField(max_length=10)
    size = models.CharField(max_length=10, blank=True, null=True)
    quantity = models.IntegerField(default=1)
    order_notes = models.TextField(blank=True, null=True)
    
    # --- Order status ---
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    # --- Tracking fields ---
    tracking_number = models.CharField(max_length=30, unique=True, blank=True, null=True)
    tracking_company = models.CharField(max_length=50, blank=True, null=True)
    estimated_delivery_days = models.IntegerField(default=5, blank=True, null=True)
    estimated_delivery_date = models.DateField(blank=True, null=True)
    shipped_at = models.DateTimeField(blank=True, null=True)
    delivered_at = models.DateTimeField(blank=True, null=True)
    
    # --- Delay handling ---
    is_delayed = models.BooleanField(default=False)
    delay_days = models.IntegerField(blank=True, null=True)
    revised_delivery_date = models.DateField(blank=True, null=True)

    delivery_confirmation_requested_at = models.DateTimeField(blank=True, null=True)
    buyer_delivery_response_at = models.DateTimeField(blank=True, null=True)

    # --- Escrow fields ---
    fund_status = models.CharField(max_length=20, choices=FUND_STATUS_CHOICES, default='HELD')
    payment_held_at = models.DateTimeField(default=timezone.now)
    funds_released_at = models.DateTimeField(blank=True, null=True)
    funds_refunded_at = models.DateTimeField(blank=True, null=True)
    inspection_deadline = models.DateTimeField(blank=True, null=True)
    escrow_notes = models.TextField(blank=True, null=True)
    
    # 👇 NEW: Return-to-Seller Fields
    return_tracking_number = models.CharField(max_length=100, blank=True, null=True)
    return_carrier = models.CharField(max_length=50, blank=True, null=True)
    return_tracking_url = models.URLField(max_length=500, blank=True, null=True)
    return_shipped_at = models.DateTimeField(blank=True, null=True)
    return_received_at = models.DateTimeField(blank=True, null=True)
    return_confirmation_deadline = models.DateTimeField(blank=True, null=True)

    RETURN_STATUS_CHOICES = [
        ('INITIATED', 'Return Initiated'),
        ('IN_TRANSIT', 'In Transit'),
        ('OUT_FOR_DELIVERY', 'Out for Delivery'),
        ('RECEIVED', 'Received by Seller'),
    ]
    return_status = models.CharField(
        max_length=20,
        choices=RETURN_STATUS_CHOICES,
        blank=True,
        null=True,
    )
    
    # --- Notification flags ---
    admin_notified = models.BooleanField(default=False)
    seller_notified = models.BooleanField(default=False)
    
    # --- Timestamps ---
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # --- Overridden save ---
    def save(self, *args, **kwargs):
        if not self.tracking_number:
            year = timezone.now().year
            count = Order.objects.filter(created_at__year=year).count() + 1
            self.tracking_number = f"ORD-{year}-{count:04d}"
        
        if self.shipped_at and self.estimated_delivery_days:
            self.estimated_delivery_date = (
                self.shipped_at.date() + timedelta(days=self.estimated_delivery_days)
            )
        
        super().save(*args, **kwargs)
    
    # ============================================ #
    # HELPER PROPERTIES                            #
    # ============================================ #
    @property
    def effective_delivery_deadline(self):
        return self.revised_delivery_date or self.estimated_delivery_date
    
    @property
    def is_ready_to_release(self):
        if self.fund_status != 'HELD':
            return False
        if self.status != 'DELIVERED':
            return False
        if not self.delivered_at:
            return False
        inspection_deadline = self.delivered_at + timedelta(hours=24)
        return timezone.now() >= inspection_deadline
    
    @property
    def is_ready_to_refund(self):
        if self.fund_status != 'HELD':
            return False
        if self.status in ['DELIVERED', 'COMPLETED']:
            return False
        deadline = self.effective_delivery_deadline
        if not deadline:
            return False
        return timezone.now().date() > deadline
    
    @property
    def days_until_deadline(self):
        deadline = self.effective_delivery_deadline
        if not deadline:
            return None
        return (deadline - timezone.now().date()).days
    
    # 👇 NEW: Return deadline properties
    @property
    def is_return_deadline_passed(self):
        """True if the seller's 48h window to confirm return has expired."""
        if not self.return_confirmation_deadline:
            return False
        return timezone.now() >= self.return_confirmation_deadline

    @property
    def hours_until_return_deadline(self):
        """Hours left for the seller to confirm receipt."""
        if not self.return_confirmation_deadline:
            return None
        delta = self.return_confirmation_deadline - timezone.now()
        return max(0, int(delta.total_seconds() // 3600))
    
    def __str__(self):
        return f"Order #{self.id} - {self.tracking_number} - {self.buyer.username}"

    @property
    def return_tracking_steps(self):
        """Returns a list of timeline steps for the return shipment."""
        if not self.return_shipped_at:
            return []
        
        s = self.return_status or 'INITIATED'
        
        order_steps = ['INITIATED', 'IN_TRANSIT', 'OUT_FOR_DELIVERY', 'RECEIVED']
        current_index = order_steps.index(s) if s in order_steps else 0
        
        steps = [
            {
                'label': 'Return Initiated',
                'detail': f'{self.return_carrier} — {self.return_tracking_number}',
                'time': self.return_shipped_at,
                'state': 'done' if current_index >= 0 else 'pending',
            },
            {
                'label': 'In Transit',
                'detail': 'Return package picked up by carrier',
                'time': None,
                'state': 'done' if current_index >= 1 else ('active' if current_index == 0 else 'pending'),
            },
            {
                'label': 'Out for Delivery',
                'detail': 'Arriving at seller',
                'time': None,
                'state': 'done' if current_index >= 2 else ('active' if current_index == 1 else 'pending'),
            },
            {
                'label': 'Received by Seller',
                'detail': 'Return received',
                'time': self.return_received_at,
                'state': 'done' if current_index >= 3 else ('active' if current_index == 2 else 'pending'),
            },
        ]
        
        return steps


# ============================================ #
# NOTIFICATION MODEL                           #
# ============================================ #
class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('FUND_RELEASED', 'Funds Released'),
        ('FUND_REFUNDED', 'Funds Refunded'),
        ('ORDER_PLACED', 'New Order Placed'),
        ('ORDER_DELAYED', 'Order Delayed'),
        ('ORDER_DELIVERED', 'Order Delivered'),
        ('ORDER_OUT_FOR_DELIVERY', 'Order Out for Delivery'), 
        ('ORDER_DISPUTED', 'Order Disputed'),
        ('DISPUTE_RESOLVED', 'Dispute Resolved'),
        ('RETURN_TRACKING_SUBMITTED', 'Return Tracking Submitted'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    order = models.ForeignKey(Order, on_delete=models.CASCADE, null=True, blank=True)
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    amount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.title}"


# ============================================ #
# DISPUTE MODEL (AI-POWERED)                   #
# ============================================ #
class Dispute(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending Review'),
        ('APPROVED', 'Approved - Refund Issued'),
        ('REJECTED', 'Rejected - Original Product Confirmed'),
    ]
    
    VERDICT_CHOICES = [
        ('ACCEPT', 'AI Recommends: Accept Dispute'),
        ('REVIEW', 'AI Recommends: Manual Review'),
        ('REJECT', 'AI Recommends: Reject Dispute'),
    ]
    
    # --- Relationships ---
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='disputes')
    buyer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='disputes')
    
    # --- Buyer input ---
    reason = models.TextField()
    received_image = models.ImageField(upload_to='disputes/received/', blank=True, null=True)
    tag_image = models.ImageField(upload_to='disputes/tags/', blank=True, null=True)
    selected_keywords = models.TextField(blank=True, null=True)
    
    # --- AI Analysis Results ---
    ai_image_score = models.IntegerField(default=0)
    ai_text_score = models.IntegerField(default=0)
    ai_final_score = models.IntegerField(default=0)
    ai_verdict = models.CharField(max_length=20, choices=VERDICT_CHOICES, blank=True, null=True)
    ai_matched_keywords = models.TextField(blank=True, null=True)
    ai_analyzed_at = models.DateTimeField(blank=True, null=True)
    ai_similarity_percent = models.IntegerField(default=100)
    ai_size_mismatch = models.BooleanField(default=False)
    ai_detected_size_text = models.TextField(blank=True, null=True)
    
    # --- Admin decision ---
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    admin_notes = models.TextField(blank=True, null=True)
    reviewed_at = models.DateTimeField(blank=True, null=True)
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_disputes'
    )
    
    # --- Timestamps ---
    created_at = models.DateTimeField(auto_now_add=True)
    
    # 👇 NEW: Property to split matched keywords for template rendering
    @property
    def matched_keywords_list(self):
        """Splits the comma-separated string into a list for the template."""
        if self.ai_matched_keywords:
            return [kw.strip() for kw in self.ai_matched_keywords.split(',') if kw.strip()]
        return []
    
    def __str__(self):
        return f"Dispute #{self.id} - Order #{self.order.id} - {self.status}"


# ============================================ #
# DISPUTE EVIDENCE MODEL (MULTIPLE UPLOADS)    #
# ============================================ #
class DisputeEvidence(models.Model):
    dispute = models.ForeignKey(Dispute, on_delete=models.CASCADE, related_name='evidences')
    file = models.FileField(upload_to='disputes/evidence/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Evidence for Dispute #{self.dispute.id}"

    RETURN_STATUS_CHOICES = [
        ('INITIATED', 'Return Initiated'),
        ('IN_TRANSIT', 'In Transit'),
        ('OUT_FOR_DELIVERY', 'Out for Delivery'),
        ('RECEIVED', 'Received by Seller'),
    ]
    return_status = models.CharField(
        max_length=20,
        choices=RETURN_STATUS_CHOICES,
        blank=True,
        null=True,
    )
    
    # --- Helper property ---
    @property
    def return_tracking_steps(self):
        """Returns a list of timeline steps for the return shipment."""
        if not self.return_shipped_at:
            return []
        
        s = self.return_status or 'INITIATED'
        
        order_steps = ['INITIATED', 'IN_TRANSIT', 'OUT_FOR_DELIVERY', 'RECEIVED']
        current_index = order_steps.index(s) if s in order_steps else 0
        
        steps = [
            {
                'label': 'Return Initiated',
                'detail': f'{self.return_carrier} — {self.return_tracking_number}',
                'time': self.return_shipped_at,
                'state': 'done' if current_index >= 0 else 'pending',
            },
            {
                'label': 'In Transit',
                'detail': 'Return package picked up by carrier',
                'time': None,
                'state': 'done' if current_index >= 1 else ('active' if current_index == 0 else 'pending'),
            },
            {
                'label': 'Out for Delivery',
                'detail': 'Arriving at seller',
                'time': None,
                'state': 'done' if current_index >= 2 else ('active' if current_index == 1 else 'pending'),
            },
            {
                'label': 'Received by Seller',
                'detail': 'Return received',
                'time': self.return_received_at,
                'state': 'done' if current_index >= 3 else ('active' if current_index == 2 else 'pending'),
            },
        ]
        
        return steps