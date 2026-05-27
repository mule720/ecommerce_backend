"""
Returns Service - GraphQL Schema
Extends return functionality with additional queries and mutations
Note: ReturnRequestType is imported from order_service to avoid duplication
"""
import graphene
from graphene_django import DjangoObjectType
from graphql import GraphQLError
from django.utils import timezone

# Import the already-defined model and type from order_service
from order_service.models import ReturnRequest
from order_service.schema import ReturnRequestType
from .models import ReturnShipment, ReturnHistory


class ReturnShipmentType(DjangoObjectType):
    """GraphQL type for ReturnShipment"""
    
    class Meta:
        model = ReturnShipment
        fields = ['id', 'return_request', 'tracking_number', 'carrier', 'sent_at', 'received_at']


class ReturnHistoryType(DjangoObjectType):
    """GraphQL type for ReturnHistory"""
    
    class Meta:
        model = ReturnHistory
        fields = ['id', 'return_request', 'status_from', 'status_to', 'changed_by', 'reason', 'changed_at']


class ReturnsQuery(graphene.ObjectType):
    """Return service queries - returns-service specific functionality"""
    
    # Return history and shipment tracking queries
    return_shipment = graphene.Field(
        ReturnShipmentType,
        tracking_number=graphene.String(required=True)
    )
    return_history = graphene.List(
        ReturnHistoryType,
        return_id=graphene.Int(required=True)
    )
    my_return_shipments = graphene.List(ReturnShipmentType)
    
    @staticmethod
    def resolve_return_shipment(obj, info, tracking_number):
        """Get return shipment by tracking number"""
        try:
            return ReturnShipment.objects.select_related('return_request').get(
                tracking_number=tracking_number
            )
        except ReturnShipment.DoesNotExist:
            return None
    
    @staticmethod
    def resolve_return_history(obj, info, return_id):
        """Get history for a return request"""
        if not info.context.user.is_authenticated:
            raise GraphQLError('Not authenticated')
        
        try:
            return_request = ReturnRequest.objects.get(id=return_id)
            
            # Check permissions
            if return_request.customer != info.context.user and not info.context.user.is_staff:
                raise GraphQLError('Permission denied')
            
            return ReturnHistory.objects.filter(
                return_request=return_request
            ).order_by('-changed_at')
        except ReturnRequest.DoesNotExist:
            return []
    
    @staticmethod
    def resolve_my_return_shipments(obj, info):
        """Get current user's return shipments"""
        if not info.context.user.is_authenticated:
            return []
        
        return ReturnShipment.objects.filter(
            return_request__customer=info.context.user
        ).select_related('return_request').order_by('-sent_at')


# Note: CreateReturnRequest mutation is handled by order_service.CreateReturnRequestMutation
# to avoid duplication. This service provides admin mutations.


class ApproveReturnMutation(graphene.Mutation):
    """Approve a return request"""
    
    class Arguments:
        return_id = graphene.Int(required=True)
        refund_amount = graphene.Decimal()
    
    success = graphene.Boolean()
    message = graphene.String()
    return_request = graphene.Field(ReturnRequestType)
    
    @staticmethod
    def mutate(root, info, return_id, refund_amount=None):
        """Approve a return"""
        if not info.context.user.is_staff:
            return ApproveReturnMutation(success=False, message='Permission denied')
        
        try:
            return_request = ReturnRequest.objects.get(id=return_id)
            
            old_status = return_request.status
            return_request.status = 'approved'
            return_request.approved_at = timezone.now()
            
            if refund_amount:
                return_request.refund_amount = refund_amount
            
            return_request.save()
            
            # Create history entry
            ReturnHistory.objects.create(
                return_request=return_request,
                status_from=old_status,
                status_to='approved',
                changed_by=info.context.user,
                reason='Return approved'
            )
            
            return ApproveReturnMutation(
                success=True,
                message='Return approved',
                return_request=return_request
            )
        except ReturnRequest.DoesNotExist:
            return ApproveReturnMutation(success=False, message='Return not found')


class RejectReturnMutation(graphene.Mutation):
    """Reject a return request"""
    
    class Arguments:
        return_id = graphene.Int(required=True)
        reason = graphene.String()
    
    success = graphene.Boolean()
    message = graphene.String()
    
    @staticmethod
    def mutate(root, info, return_id, reason=''):
        """Reject a return"""
        if not info.context.user.is_staff:
            return RejectReturnMutation(success=False, message='Permission denied')
        
        try:
            return_request = ReturnRequest.objects.get(id=return_id)
            
            old_status = return_request.status
            return_request.status = 'rejected'
            return_request.save()
            
            # Create history entry
            ReturnHistory.objects.create(
                return_request=return_request,
                status_from=old_status,
                status_to='rejected',
                changed_by=info.context.user,
                reason=reason
            )
            
            return RejectReturnMutation(success=True, message='Return rejected')
        except ReturnRequest.DoesNotExist:
            return RejectReturnMutation(success=False, message='Return not found')


class IssueRefundMutation(graphene.Mutation):
    """Issue refund for an approved return"""
    
    class Arguments:
        return_id = graphene.Int(required=True)
    
    success = graphene.Boolean()
    message = graphene.String()
    return_request = graphene.Field(ReturnRequestType)
    
    @staticmethod
    def mutate(root, info, return_id):
        """Issue refund"""
        if not info.context.user.is_staff:
            return IssueRefundMutation(success=False, message='Permission denied')
        
        try:
            return_request = ReturnRequest.objects.get(id=return_id)
            
            if return_request.status != 'approved':
                return IssueRefundMutation(
                    success=False,
                    message='Can only refund approved returns'
                )
            
            return_request.refund_issued = True
            return_request.refund_date = timezone.now()
            return_request.status = 'refunded'
            return_request.save()
            
            # Create history entry
            ReturnHistory.objects.create(
                return_request=return_request,
                status_from='approved',
                status_to='refunded',
                changed_by=info.context.user,
                reason=f'Refund issued: {return_request.refund_amount}'
            )
            
            return IssueRefundMutation(
                success=True,
                message='Refund issued',
                return_request=return_request
            )
        except ReturnRequest.DoesNotExist:
            return IssueRefundMutation(success=False, message='Return not found')


class ReturnsMutation(graphene.ObjectType):
    """Return service mutations - admin-only operations for returns management"""
    
    # Note: create_return_request is handled by order_service
    approve_return = ApproveReturnMutation.Field()
    reject_return = RejectReturnMutation.Field()
    issue_refund = IssueRefundMutation.Field()
