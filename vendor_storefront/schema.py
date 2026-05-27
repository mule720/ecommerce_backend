"""
Vendor Storefront GraphQL Schema
Public queries + authenticated vendor mutations for storefront customisation,
product browsing, and cross-vendor price comparison.
"""
import graphene
from graphene_django import DjangoObjectType
from django.db.models import Q, Avg
from django.contrib.auth import get_user_model

from .models import VendorStorefront, StorefrontSection, StorefrontReview
from product_service.models import Product, Category
from user_service.models import VendorProfile

User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
# Object Types
# ─────────────────────────────────────────────────────────────────────────────

class StorefrontSectionType(DjangoObjectType):
    class Meta:
        model = StorefrontSection
        fields = '__all__'


class StorefrontReviewType(DjangoObjectType):
    class Meta:
        model = StorefrontReview
        fields = '__all__'


class VendorStorefrontType(DjangoObjectType):
    class Meta:
        model = VendorStorefront
        fields = '__all__'

    # Extra computed fields
    vendor_name        = graphene.String()
    vendor_id          = graphene.ID()
    business_name      = graphene.String()
    business_description = graphene.String()
    vendor_rating      = graphene.Float()
    total_products     = graphene.Int()
    average_review     = graphene.Float()
    review_count       = graphene.Int()

    def resolve_vendor_name(self, info):
        return self.vendor.get_full_name() or self.vendor.username

    def resolve_vendor_id(self, info):
        return self.vendor.id

    def resolve_business_name(self, info):
        try:
            return self.vendor.vendor_profile.business_name
        except Exception:
            return self.vendor.username

    def resolve_business_description(self, info):
        try:
            return self.vendor.vendor_profile.business_description
        except Exception:
            return ''

    def resolve_vendor_rating(self, info):
        try:
            return float(self.vendor.vendor_profile.rating)
        except Exception:
            return 0.0

    def resolve_total_products(self, info):
        return Product.objects.filter(vendor=self.vendor, status='active').count()

    def resolve_average_review(self, info):
        agg = self.vendor_reviews.filter(is_approved=True).aggregate(avg=Avg('rating'))
        return float(agg['avg'] or 0)

    def resolve_review_count(self, info):
        return self.vendor_reviews.filter(is_approved=True).count()


# Light product type for storefront (avoids importing the full ProductType relay node)
class StorefrontProductType(graphene.ObjectType):
    id            = graphene.ID()
    name          = graphene.String()
    slug          = graphene.String()
    price         = graphene.Float()
    compare_at_price = graphene.Float()
    main_image    = graphene.String()
    rating        = graphene.Float()
    review_count  = graphene.Int()
    quantity      = graphene.Int()
    category_name = graphene.String()
    sku           = graphene.String()
    description   = graphene.String()


def _serialize_product(p: Product) -> StorefrontProductType:
    img = p.images.filter(is_primary=True).first() or p.images.first()
    if img:
        main_image = img.external_url or (img.image.url if img.image else '')
    else:
        main_image = ''

    reviews = p.reviews.filter(is_approved=True)
    avg_rating = (sum(r.rating for r in reviews) / reviews.count()) if reviews.exists() else 0

    return StorefrontProductType(
        id=p.id,
        name=p.name,
        slug=p.slug,
        price=float(p.price),
        compare_at_price=float(p.compare_at_price) if p.compare_at_price else None,
        main_image=main_image,
        rating=round(avg_rating, 1),
        review_count=reviews.count(),
        quantity=p.quantity,
        category_name=p.category.name if p.category else '',
        sku=p.sku,
        description=p.description,
    )


class StorefrontProductsResult(graphene.ObjectType):
    products    = graphene.List(StorefrontProductType)
    total_count = graphene.Int()
    has_next    = graphene.Boolean()


class PriceComparisonItem(graphene.ObjectType):
    """Single product listing in a price comparison result."""
    product_id    = graphene.ID()
    product_name  = graphene.String()
    product_slug  = graphene.String()
    price         = graphene.Float()
    compare_at_price = graphene.Float()
    main_image    = graphene.String()
    vendor_id     = graphene.ID()
    vendor_name   = graphene.String()
    storefront_slug = graphene.String()
    rating        = graphene.Float()
    in_stock      = graphene.Boolean()


# ─────────────────────────────────────────────────────────────────────────────
# Queries
# ─────────────────────────────────────────────────────────────────────────────

class StorefrontQuery(graphene.ObjectType):

    # Public: single storefront by slug or vendor id
    vendor_storefront = graphene.Field(
        VendorStorefrontType,
        slug=graphene.String(),
        vendor_id=graphene.ID(),
    )

    # Public: list all published storefronts
    all_storefronts = graphene.List(
        VendorStorefrontType,
        search=graphene.String(),
        first=graphene.Int(default_value=20),
        offset=graphene.Int(default_value=0),
    )

    # Public: products within a specific storefront
    storefront_products = graphene.Field(
        StorefrontProductsResult,
        vendor_id=graphene.ID(),
        slug=graphene.String(),
        search=graphene.String(),
        category_id=graphene.ID(),
        sort_by=graphene.String(default_value='newest'),  # newest | price_asc | price_desc | rating
        first=graphene.Int(default_value=20),
        offset=graphene.Int(default_value=0),
    )

    # Public: compare same/similar products across vendors
    compare_prices = graphene.List(
        PriceComparisonItem,
        product_name=graphene.String(),
        category_id=graphene.ID(),
        exclude_vendor_id=graphene.ID(),
    )

    # Authenticated: get current vendor's own storefront
    my_storefront = graphene.Field(VendorStorefrontType)

    # ── Resolvers ────────────────────────────────────────────────────────

    def resolve_vendor_storefront(self, info, slug=None, vendor_id=None):
        qs = VendorStorefront.objects.filter(is_published=True)
        if slug:
            return qs.filter(slug=slug).first()
        if vendor_id:
            return qs.filter(vendor_id=vendor_id).first()
        return None

    def resolve_all_storefronts(self, info, search=None, first=20, offset=0):
        qs = VendorStorefront.objects.filter(is_published=True)
        if search:
            qs = qs.filter(
                Q(tagline__icontains=search) |
                Q(vendor__vendor_profile__business_name__icontains=search) |
                Q(vendor__username__icontains=search)
            )
        return qs[offset: offset + first]

    def resolve_storefront_products(self, info, vendor_id=None, slug=None,
                                    search=None, category_id=None,
                                    sort_by='newest', first=20, offset=0):
        # Resolve vendor
        if slug:
            sf = VendorStorefront.objects.filter(slug=slug).first()
            if not sf:
                return StorefrontProductsResult(products=[], total_count=0, has_next=False)
            vendor_id = sf.vendor_id

        if not vendor_id:
            return StorefrontProductsResult(products=[], total_count=0, has_next=False)

        qs = Product.objects.filter(vendor_id=vendor_id, status='active')

        if search:
            qs = qs.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search) |
                Q(sku__icontains=search)
            )
        if category_id:
            qs = qs.filter(category_id=category_id)

        sort_map = {
            'newest':     '-created_at',
            'oldest':     'created_at',
            'price_asc':  'price',
            'price_desc': '-price',
            'name_asc':   'name',
        }
        qs = qs.order_by(sort_map.get(sort_by, '-created_at'))

        total = qs.count()
        page  = qs.prefetch_related('images', 'reviews')[offset: offset + first]
        products = [_serialize_product(p) for p in page]

        return StorefrontProductsResult(
            products=products,
            total_count=total,
            has_next=(offset + first) < total,
        )

    def resolve_compare_prices(self, info, product_name=None, category_id=None, exclude_vendor_id=None):
        """
        Find similar/same-named products from OTHER vendors so customers can compare prices.
        """
        if not product_name and not category_id:
            return []

        qs = Product.objects.filter(status='active').select_related('vendor').prefetch_related('images', 'reviews')

        if product_name:
            qs = qs.filter(name__icontains=product_name)
        if category_id:
            qs = qs.filter(category_id=category_id)
        if exclude_vendor_id:
            qs = qs.exclude(vendor_id=exclude_vendor_id)

        results = []
        for p in qs[:30]:
            img = p.images.filter(is_primary=True).first() or p.images.first()
            main_image = ''
            if img:
                main_image = img.external_url or (img.image.url if img.image else '')

            reviews = p.reviews.filter(is_approved=True)
            avg_rating = (sum(r.rating for r in reviews) / reviews.count()) if reviews.exists() else 0

            # Get storefront slug if vendor has one
            sf_slug = ''
            try:
                sf_slug = p.vendor.storefront.slug
            except Exception:
                pass

            vendor_name = ''
            try:
                vendor_name = p.vendor.vendor_profile.business_name
            except Exception:
                vendor_name = p.vendor.username

            results.append(PriceComparisonItem(
                product_id=p.id,
                product_name=p.name,
                product_slug=p.slug,
                price=float(p.price),
                compare_at_price=float(p.compare_at_price) if p.compare_at_price else None,
                main_image=main_image,
                vendor_id=p.vendor_id,
                vendor_name=vendor_name,
                storefront_slug=sf_slug,
                rating=round(avg_rating, 1),
                in_stock=p.quantity > 0,
            ))

        # Sort by price ascending so cheapest is first
        results.sort(key=lambda x: x.price)
        return results

    def resolve_my_storefront(self, info):
        user = info.context.user
        if not user or not user.is_authenticated:
            return None
        try:
            return user.storefront
        except VendorStorefront.DoesNotExist:
            return None


# ─────────────────────────────────────────────────────────────────────────────
# Mutations
# ─────────────────────────────────────────────────────────────────────────────

class StorefrontResult(graphene.ObjectType):
    success    = graphene.Boolean()
    message    = graphene.String()
    storefront = graphene.Field(VendorStorefrontType)


class UpdateVendorStorefront(graphene.Mutation):
    """Create-or-update the authenticated vendor's storefront."""

    class Arguments:
        slug              = graphene.String()
        tagline           = graphene.String()
        banner_url        = graphene.String()
        logo_url          = graphene.String()
        announcement      = graphene.String()
        template          = graphene.String()
        primary_color     = graphene.String()
        secondary_color   = graphene.String()
        bg_color          = graphene.String()
        text_color        = graphene.String()
        show_featured_section  = graphene.Boolean()
        show_categories_filter = graphene.Boolean()
        show_search_bar        = graphene.Boolean()
        products_per_row  = graphene.Int()
        website_url       = graphene.String()
        facebook_url      = graphene.String()
        instagram_url     = graphene.String()
        twitter_url       = graphene.String()

    Output = StorefrontResult

    def mutate(self, info, **kwargs):
        user = info.context.user
        if not user or not user.is_authenticated:
            return StorefrontResult(success=False, message='Authentication required.')
        if user.role not in ('vendor', 'admin'):
            return StorefrontResult(success=False, message='Only vendors can manage a storefront.')

        sf, _ = VendorStorefront.objects.get_or_create(vendor=user)

        # Apply all supplied fields
        allowed = [
            'tagline', 'banner_url', 'logo_url', 'announcement',
            'template', 'primary_color', 'secondary_color', 'bg_color', 'text_color',
            'show_featured_section', 'show_categories_filter', 'show_search_bar',
            'products_per_row', 'website_url', 'facebook_url', 'instagram_url', 'twitter_url',
        ]
        for field in allowed:
            if field in kwargs and kwargs[field] is not None:
                setattr(sf, field, kwargs[field])

        # Slug change (validated for uniqueness)
        if 'slug' in kwargs and kwargs['slug']:
            from django.utils.text import slugify
            new_slug = slugify(kwargs['slug'])[:100]
            if VendorStorefront.objects.filter(slug=new_slug).exclude(pk=sf.pk).exists():
                return StorefrontResult(success=False, message=f'Slug "{new_slug}" is already taken.')
            sf.slug = new_slug

        sf.save()
        return StorefrontResult(success=True, message='Storefront updated.', storefront=sf)


class PublishStorefront(graphene.Mutation):
    """Toggle the published status of the vendor's storefront."""

    class Arguments:
        publish = graphene.Boolean(required=True)

    Output = StorefrontResult

    def mutate(self, info, publish):
        user = info.context.user
        if not user or not user.is_authenticated:
            return StorefrontResult(success=False, message='Authentication required.')

        try:
            sf = user.storefront
        except VendorStorefront.DoesNotExist:
            return StorefrontResult(success=False, message='No storefront found. Please create one first.')

        sf.is_published = publish
        sf.save(update_fields=['is_published', 'updated_at'])
        status = 'published' if publish else 'unpublished'
        return StorefrontResult(success=True, message=f'Storefront {status}.', storefront=sf)


class AddStorefrontSection(graphene.Mutation):
    class Arguments:
        section_type = graphene.String(required=True)
        title        = graphene.String()
        content      = graphene.String()
        image_url    = graphene.String()
        link_url     = graphene.String()
        sort_order   = graphene.Int()

    class Output(graphene.ObjectType):
        success = graphene.Boolean()
        message = graphene.String()
        section = graphene.Field(StorefrontSectionType)

    def mutate(self, info, section_type, title='', content='',
               image_url='', link_url='', sort_order=0):
        user = info.context.user
        if not user or not user.is_authenticated:
            return AddStorefrontSection.Output(success=False, message='Auth required.')

        try:
            sf = user.storefront
        except VendorStorefront.DoesNotExist:
            return AddStorefrontSection.Output(success=False, message='No storefront found.')

        valid_types = [c[0] for c in StorefrontSection.SectionType.choices]
        if section_type not in valid_types:
            return AddStorefrontSection.Output(success=False, message=f'Invalid section type "{section_type}".')

        section = StorefrontSection.objects.create(
            storefront=sf,
            section_type=section_type,
            title=title,
            content=content,
            image_url=image_url,
            link_url=link_url,
            sort_order=sort_order,
        )
        return AddStorefrontSection.Output(success=True, message='Section added.', section=section)


class DeleteStorefrontSection(graphene.Mutation):
    class Arguments:
        section_id = graphene.ID(required=True)

    class Output(graphene.ObjectType):
        success = graphene.Boolean()
        message = graphene.String()

    def mutate(self, info, section_id):
        user = info.context.user
        if not user or not user.is_authenticated:
            return DeleteStorefrontSection.Output(success=False, message='Auth required.')

        try:
            sf = user.storefront
            section = sf.sections.get(id=section_id)
            section.delete()
            return DeleteStorefrontSection.Output(success=True, message='Section deleted.')
        except (VendorStorefront.DoesNotExist, StorefrontSection.DoesNotExist):
            return DeleteStorefrontSection.Output(success=False, message='Section not found.')


class LeaveStorefrontReview(graphene.Mutation):
    class Arguments:
        vendor_id = graphene.ID(required=True)
        rating    = graphene.Int(required=True)
        title     = graphene.String()
        comment   = graphene.String(required=True)

    class Output(graphene.ObjectType):
        success = graphene.Boolean()
        message = graphene.String()

    def mutate(self, info, vendor_id, rating, comment, title=''):
        user = info.context.user
        if not user or not user.is_authenticated:
            return LeaveStorefrontReview.Output(success=False, message='Auth required.')

        if not (1 <= rating <= 5):
            return LeaveStorefrontReview.Output(success=False, message='Rating must be 1–5.')

        try:
            sf = VendorStorefront.objects.get(vendor_id=vendor_id)
        except VendorStorefront.DoesNotExist:
            return LeaveStorefrontReview.Output(success=False, message='Vendor storefront not found.')

        review, created = StorefrontReview.objects.update_or_create(
            storefront=sf,
            reviewer=user,
            defaults=dict(rating=rating, title=title, comment=comment, is_approved=False),
        )
        msg = 'Review submitted (pending approval).' if created else 'Review updated (pending approval).'
        return LeaveStorefrontReview.Output(success=True, message=msg)


class StorefrontMutation(graphene.ObjectType):
    update_vendor_storefront  = UpdateVendorStorefront.Field()
    publish_storefront        = PublishStorefront.Field()
    add_storefront_section    = AddStorefrontSection.Field()
    delete_storefront_section = DeleteStorefrontSection.Field()
    leave_storefront_review   = LeaveStorefrontReview.Field()
