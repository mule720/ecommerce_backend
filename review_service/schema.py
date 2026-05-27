"""
Review Service - GraphQL Schema
"""

import graphene
from django.db.models import Avg, Q
from decimal import Decimal

from .models import Review, ReviewHelpful, ReviewModerationQueue, ReviewTag
from product_service.models import Product


class ReviewStatistics(graphene.ObjectType):
    """Defines the purpose and behavior of the `ReviewStatistics` class."""
    average_rating = graphene.Decimal()
    total_reviews = graphene.Int()
    rating_distribution = graphene.JSONString()
    
    average_quality = graphene.Decimal()
    average_value = graphene.Decimal()
    average_shipping = graphene.Decimal()
    
    verified_count = graphene.Int()


class ReviewType(graphene.ObjectType):
    """GraphQL type that exposes the `Review` model fields to API clients."""
    id = graphene.Int()
    product_id = graphene.Int()
    reviewer_name = graphene.String()
    reviewer_avatar = graphene.String()
    
    rating = graphene.Int()
    quality_rating = graphene.Int()
    value_rating = graphene.Int()
    shipping_rating = graphene.Int()
    
    title = graphene.String()
    body = graphene.String()
    
    images = graphene.List(graphene.String)
    video_url = graphene.String()
    
    helpful_count = graphene.Int()
    unhelpful_count = graphene.Int()
    is_helpful_to_me = graphene.Boolean()
    
    seller_response = graphene.String()
    seller_response_at = graphene.DateTime()
    
    is_verified_purchase = graphene.Boolean()
    created_at = graphene.DateTime()


class ReviewQuery(graphene.ObjectType):
    """Groups GraphQL read operations (queries) for this module."""
    product_reviews = graphene.List(
        ReviewType,
        product_id=graphene.Int(required=True),
        rating=graphene.Int(),
        verified_only=graphene.Boolean(),
        sort_by=graphene.String(),
        limit=graphene.Int(),
        offset=graphene.Int(),
    )
    
    review_statistics = graphene.Field(
        ReviewStatistics,
        product_id=graphene.Int(required=True)
    )
    
    my_reviews = graphene.List(ReviewType)
    
    single_review = graphene.Field(
        ReviewType,
        review_id=graphene.Int(required=True)
    )
    
    @staticmethod
    def resolve_product_reviews(
        obj, info,
        product_id,
        rating=None,
        verified_only=False,
        sort_by='helpful',
        limit=10,
        offset=0
    ):
        """Resolver for the GraphQL field `product reviews`."""
        reviews = Review.objects.filter(
            product_id=product_id,
            status='published'
        ).select_related('reviewer')
        
        if rating:
            reviews = reviews.filter(rating=rating)
        
        if verified_only:
            reviews = reviews.filter(is_verified_purchase=True)
        
        # Sorting
        if sort_by == 'recent':
            reviews = reviews.order_by('-created_at')
        elif sort_by == 'rating_high':
            reviews = reviews.order_by('-rating')
        elif sort_by == 'rating_low':
            reviews = reviews.order_by('rating')
        else:  # helpful (default)
            reviews = reviews.order_by('-helpful_count')
        
        user_votes = {}
        if info.context.user.is_authenticated:
            votes = ReviewHelpful.objects.filter(
                user=info.context.user
            ).values('review_id', 'vote_type')
            user_votes = {v['review_id']: v['vote_type'] for v in votes}
        
        # Pagination
        items = reviews[offset:offset+limit]
        
        result = []
        for review in items:
            result.append(ReviewType(
                id=review.id,
                product_id=review.product_id,
                reviewer_name=review.reviewer.username,
                reviewer_avatar=review.reviewer.profile.avatar.url if hasattr(review.reviewer, 'profile') and review.reviewer.profile.avatar else None,
                rating=review.rating,
                quality_rating=review.quality_rating,
                value_rating=review.value_rating,
                shipping_rating=review.shipping_rating,
                title=review.title,
                body=review.body,
                images=review.images,
                video_url=review.video_url,
                helpful_count=review.helpful_count,
                unhelpful_count=review.unhelpful_count,
                is_helpful_to_me=user_votes.get(review.id) == 'helpful',
                seller_response=review.seller_response,
                seller_response_at=review.seller_response_at,
                is_verified_purchase=review.is_verified_purchase,
                created_at=review.created_at,
            ))
        
        return result
    
    @staticmethod
    def resolve_review_statistics(obj, info, product_id):
        """Resolver for the GraphQL field `review statistics`."""
        reviews = Review.objects.filter(
            product_id=product_id,
            status='published'
        )
        
        if not reviews.exists():
            return ReviewStatistics(
                average_rating=Decimal('0'),
                total_reviews=0,
                rating_distribution={},
                average_quality=Decimal('0'),
                average_value=Decimal('0'),
                average_shipping=Decimal('0'),
                verified_count=0
            )
        
        stats = reviews.aggregate(
            avg_rating=Avg('rating'),
            avg_quality=Avg('quality_rating'),
            avg_value=Avg('value_rating'),
            avg_shipping=Avg('shipping_rating'),
        )
        
        # Rating distribution
        distribution = {}
        for i in range(1, 6):
            distribution[str(i)] = reviews.filter(rating=i).count()
        
        return ReviewStatistics(
            average_rating=Decimal(str(stats['avg_rating'] or 0)),
            total_reviews=reviews.count(),
            rating_distribution=distribution,
            average_quality=Decimal(str(stats['avg_quality'] or 0)),
            average_value=Decimal(str(stats['avg_value'] or 0)),
            average_shipping=Decimal(str(stats['avg_shipping'] or 0)),
            verified_count=reviews.filter(is_verified_purchase=True).count(),
        )
    
    @staticmethod
    def resolve_my_reviews(obj, info):
        """Resolver for the GraphQL field `my reviews`."""
        if not info.context.user.is_authenticated:
            return []
        
        reviews = Review.objects.filter(
            reviewer=info.context.user
        ).order_by('-created_at')
        
        return [
            ReviewType(
                id=r.id,
                product_id=r.product_id,
                reviewer_name=r.reviewer.username,
                rating=r.rating,
                title=r.title,
                body=r.body,
                images=r.images,
                created_at=r.created_at,
                is_verified_purchase=r.is_verified_purchase,
            )
            for r in reviews
        ]
    
    @staticmethod
    def resolve_single_review(obj, info, review_id):
        """Resolver for the GraphQL field `single review`."""
        try:
            review = Review.objects.get(id=review_id, status='published')
            return ReviewType(
                id=review.id,
                product_id=review.product_id,
                reviewer_name=review.reviewer.username,
                rating=review.rating,
                title=review.title,
                body=review.body,
                created_at=review.created_at,
            )
        except Review.DoesNotExist:
            return None


class SubmitReview(graphene.Mutation):
    """Defines the purpose and behavior of the `SubmitReview` class."""
    class Arguments:
        """Defines the purpose and behavior of the `Arguments` class."""
        product_id = graphene.Int(required=True)
        rating = graphene.Int(required=True)
        quality_rating = graphene.Int(required=True)
        value_rating = graphene.Int(required=True)
        shipping_rating = graphene.Int(required=True)
        title = graphene.String(required=True)
        body = graphene.String(required=True)
        images = graphene.List(graphene.String)
        video_url = graphene.String()
    
    success = graphene.Boolean()
    message = graphene.String()
    review_id = graphene.Int()
    
    @staticmethod
    def mutate(
        root, info,
        product_id, rating, quality_rating,
        value_rating, shipping_rating,
        title, body,
        images=None, video_url=None
    ):
        """Executes mutation business rules and returns the mutation response object."""
        if not info.context.user.is_authenticated:
            return SubmitReview(success=False, message="Not authenticated")
        
        try:
            product = Product.objects.get(id=product_id)
            
            # Check if user already reviewed
            existing = Review.objects.filter(
                product=product,
                reviewer=info.context.user
            ).first()
            
            if existing:
                existing.rating = rating
                existing.quality_rating = quality_rating
                existing.value_rating = value_rating
                existing.shipping_rating = shipping_rating
                existing.title = title
                existing.body = body
                existing.images = images or []
                existing.video_url = video_url or ''
                existing.status = 'pending'
                existing.save()
                return SubmitReview(
                    success=True,
                    message="Review updated",
                    review_id=existing.id
                )
            
            review = Review.objects.create(
                product=product,
                reviewer=info.context.user,
                rating=rating,
                quality_rating=quality_rating,
                value_rating=value_rating,
                shipping_rating=shipping_rating,
                title=title,
                body=body,
                images=images or [],
                video_url=video_url or '',
                is_verified_purchase=product.orders.filter(
                    customer=info.context.user
                ).exists()
            )
            
            return SubmitReview(
                success=True,
                message="Review submitted for moderation",
                review_id=review.id
            )
        
        except Product.DoesNotExist:
            return SubmitReview(success=False, message="Product not found")


class MarkReviewHelpful(graphene.Mutation):
    """Defines the purpose and behavior of the `MarkReviewHelpful` class."""
    class Arguments:
        """Defines the purpose and behavior of the `Arguments` class."""
        review_id = graphene.Int(required=True)
        is_helpful = graphene.Boolean(required=True)
    
    success = graphene.Boolean()
    helpful_count = graphene.Int()
    unhelpful_count = graphene.Int()
    
    @staticmethod
    def mutate(root, info, review_id, is_helpful):
        """Executes mutation business rules and returns the mutation response object."""
        if not info.context.user.is_authenticated:
            return MarkReviewHelpful(success=False)
        
        try:
            review = Review.objects.get(id=review_id)
            
            vote_type = 'helpful' if is_helpful else 'unhelpful'
            vote, created = ReviewHelpful.objects.update_or_create(
                review=review,
                user=info.context.user,
                defaults={'vote_type': vote_type}
            )
            
            if created:
                if is_helpful:
                    review.helpful_count += 1
                else:
                    review.unhelpful_count += 1
            else:
                # Changed vote
                if vote.vote_type != vote_type:
                    if is_helpful:
                        review.helpful_count += 1
                        review.unhelpful_count -= 1
                    else:
                        review.unhelpful_count += 1
                        review.helpful_count -= 1
            
            review.save()
            
            return MarkReviewHelpful(
                success=True,
                helpful_count=review.helpful_count,
                unhelpful_count=review.unhelpful_count
            )
        
        except Review.DoesNotExist:
            return MarkReviewHelpful(success=False)


class RespondToReview(graphene.Mutation):
    """Defines the purpose and behavior of the `RespondToReview` class."""
    class Arguments:
        """Defines the purpose and behavior of the `Arguments` class."""
        review_id = graphene.Int(required=True)
        response = graphene.String(required=True)
    
    success = graphene.Boolean()
    message = graphene.String()
    
    @staticmethod
    def mutate(root, info, review_id, response):
        """Executes mutation business rules and returns the mutation response object."""
        if not info.context.user.is_authenticated:
            return RespondToReview(success=False, message="Not authenticated")
        
        try:
            review = Review.objects.get(id=review_id)
            
            # Check if user is the vendor
            if review.product.vendor != info.context.user:
                return RespondToReview(
                    success=False,
                    message="Only the vendor can respond"
                )
            
            from django.utils import timezone
            review.seller_response = response
            review.seller_response_at = timezone.now()
            review.save()
            
            return RespondToReview(
                success=True,
                message="Response added successfully"
            )
        
        except Review.DoesNotExist:
            return RespondToReview(success=False, message="Review not found")


class ReviewMutation(graphene.ObjectType):
    """Groups GraphQL write operations (mutations) for this module."""
    submit_review = SubmitReview.Field()
    mark_review_helpful = MarkReviewHelpful.Field()
    respond_to_review = RespondToReview.Field()
