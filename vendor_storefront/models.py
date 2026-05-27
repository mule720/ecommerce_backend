"""
Vendor Storefront Models
Each vendor can customise their own sub-site within the marketplace.
"""
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.utils.text import slugify


class StorefrontTemplate(models.TextChoices):
    MINIMAL    = 'minimal',    _('Minimal')
    BOLD       = 'bold',       _('Bold')
    ELEGANT    = 'elegant',    _('Elegant')
    VIBRANT    = 'vibrant',    _('Vibrant')
    TECH       = 'tech',       _('Tech')


class VendorStorefront(models.Model):
    """
    One storefront per vendor.  Created automatically (or lazily) the first
    time a vendor visits the customiser.
    """
    vendor = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='storefront',
    )

    # ── Identity ──────────────────────────────────────────────────────────
    slug = models.SlugField(
        max_length=120,
        unique=True,
        help_text="URL-safe identifier: /shop/<slug>",
    )
    tagline      = models.CharField(max_length=200, blank=True)
    banner_url   = models.URLField(blank=True, help_text="Hero banner image URL")
    logo_url     = models.URLField(blank=True, help_text="Storefront logo URL")
    announcement = models.CharField(
        max_length=300,
        blank=True,
        help_text="Short announcement bar text (e.g. 'Free shipping over $50')",
    )

    # ── Theme ─────────────────────────────────────────────────────────────
    template = models.CharField(
        max_length=20,
        choices=StorefrontTemplate.choices,
        default=StorefrontTemplate.MINIMAL,
    )
    # Stored as hex strings, e.g. "#6366f1"
    primary_color   = models.CharField(max_length=7, default='#6366f1')
    secondary_color = models.CharField(max_length=7, default='#f59e0b')
    bg_color        = models.CharField(max_length=7, default='#ffffff')
    text_color      = models.CharField(max_length=7, default='#111827')

    # ── Layout ────────────────────────────────────────────────────────────
    show_featured_section  = models.BooleanField(default=True)
    show_categories_filter = models.BooleanField(default=True)
    show_search_bar        = models.BooleanField(default=True)
    products_per_row       = models.IntegerField(default=4)   # 2 | 3 | 4

    # ── Social / Contact ──────────────────────────────────────────────────
    website_url   = models.URLField(blank=True)
    facebook_url  = models.URLField(blank=True)
    instagram_url = models.URLField(blank=True)
    twitter_url   = models.URLField(blank=True)

    # ── Status ────────────────────────────────────────────────────────────
    is_published  = models.BooleanField(default=False)
    is_featured   = models.BooleanField(default=False)  # admin-only: show on marketplace

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'vendor_storefronts'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.vendor.username} storefront ({self.slug})"

    def save(self, *args, **kwargs):
        # Auto-generate slug from vendor business name or username
        if not self.slug:
            base = ''
            if hasattr(self.vendor, 'vendor_profile'):
                base = self.vendor.vendor_profile.business_name
            base = base or self.vendor.username
            self.slug = slugify(base)[:100]
            # Ensure uniqueness
            original = self.slug
            n = 1
            while VendorStorefront.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                self.slug = f"{original}-{n}"
                n += 1
        super().save(*args, **kwargs)


class StorefrontSection(models.Model):
    """
    Optional custom content blocks vendors can add to their storefront
    (e.g. About Us, Promotion banners, Custom HTML).
    """

    class SectionType(models.TextChoices):
        BANNER     = 'banner',     _('Banner')
        TEXT       = 'text',       _('Text Block')
        COLLECTION = 'collection', _('Featured Collection')
        VIDEO      = 'video',      _('Video')

    storefront   = models.ForeignKey(VendorStorefront, on_delete=models.CASCADE, related_name='sections')
    section_type = models.CharField(max_length=20, choices=SectionType.choices)
    title        = models.CharField(max_length=200, blank=True)
    content      = models.TextField(blank=True)          # rich text or HTML
    image_url    = models.URLField(blank=True)
    link_url     = models.URLField(blank=True)
    sort_order   = models.IntegerField(default=0)
    is_active    = models.BooleanField(default=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'storefront_sections'
        ordering = ['sort_order']

    def __str__(self):
        return f"{self.storefront.slug} – {self.section_type} ({self.title})"


class StorefrontReview(models.Model):
    """Aggregate vendor-level reviews visible on the storefront."""
    storefront = models.ForeignKey(VendorStorefront, on_delete=models.CASCADE, related_name='vendor_reviews')
    reviewer   = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='vendor_reviews_given',
    )
    rating  = models.IntegerField(choices=[(i, i) for i in range(1, 6)])
    title   = models.CharField(max_length=200, blank=True)
    comment = models.TextField()
    is_approved = models.BooleanField(default=False)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'storefront_reviews'
        ordering = ['-created_at']
        unique_together = ['storefront', 'reviewer']

    def __str__(self):
        return f"{self.reviewer} → {self.storefront.slug} ({self.rating}★)"
