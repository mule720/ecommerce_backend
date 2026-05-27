"""
Notification Service GraphQL Schema
GraphQL API for notification management
"""
import graphene
from graphene import relay
from graphene_django import DjangoObjectType
from graphene_django.filter import DjangoFilterConnectionField
from django_filters import FilterSet, CharFilter, BooleanFilter
from datetime import datetime
from .models import Notification, EmailTemplate, EmailQueue, PushNotification


class NotificationType(DjangoObjectType):
    """GraphQL type for Notification model"""
    class Meta:
        """Defines the purpose and behavior of the `Meta` class."""
        model = Notification
        fields = "__all__"
        interfaces = (relay.Node,)
        # Avoid GraphQL type-name collision with auto-generated enum for
        # Notification.type choices (NotificationType).
        convert_choices_to_enum = False


class EmailTemplateType(DjangoObjectType):
    """GraphQL type for EmailTemplate model"""
    class Meta:
        """Defines the purpose and behavior of the `Meta` class."""
        model = EmailTemplate
        fields = "__all__"
        interfaces = (relay.Node,)


class EmailQueueType(DjangoObjectType):
    """GraphQL type for EmailQueue model"""
    class Meta:
        """Defines the purpose and behavior of the `Meta` class."""
        model = EmailQueue
        fields = "__all__"
        interfaces = (relay.Node,)


class PushNotificationType(DjangoObjectType):
    """GraphQL type for PushNotification model"""
    class Meta:
        """Defines the purpose and behavior of the `Meta` class."""
        model = PushNotification
        fields = "__all__"
        interfaces = (relay.Node,)


# Filters
class NotificationFilter(FilterSet):
    """Filter for Notification queries"""
    type = CharFilter(field_name='type')
    is_read = BooleanFilter(field_name='is_read')
    
    class Meta:
        """Defines the purpose and behavior of the `Meta` class."""
        model = Notification
        fields = ['type', 'is_read']


class Query(graphene.ObjectType):
    """Notification Service Queries"""
    
    # Notification queries
    my_notifications = DjangoFilterConnectionField(
        NotificationType,
        filterset_class=NotificationFilter
    )
    notification = relay.Node.Field(NotificationType)
    unread_notification_count = graphene.Int()
    
    # Email template queries
    all_email_templates = graphene.List(EmailTemplateType)
    email_template = graphene.Field(
        EmailTemplateType,
        id=graphene.ID(required=True)
    )
    
    # Email queue queries
    email_queue = graphene.List(EmailQueueType)
    
    # Push notification queries
    my_push_notifications = graphene.List(PushNotificationType)
    
    # Resolvers
    def resolve_my_notifications(self, info, **kwargs):
        """Resolver for the GraphQL field `my notifications`."""
        user = info.context.user
        if user.is_anonymous:
            raise Exception('Not logged in!')
        return Notification.objects.filter(user=user)
    
    def resolve_unread_notification_count(self, info):
        """Resolver for the GraphQL field `unread notification count`."""
        user = info.context.user
        if user.is_anonymous:
            return 0
        return Notification.objects.filter(user=user, is_read=False).count()
    
    def resolve_all_email_templates(self, info, **kwargs):
        """Resolver for the GraphQL field `all email templates`."""
        return EmailTemplate.objects.filter(is_active=True)
    
    def resolve_email_template(self, info, id):
        """Resolver for the GraphQL field `email template`."""
        try:
            return EmailTemplate.objects.get(pk=int(id))
        except (EmailTemplate.DoesNotExist, ValueError):
            return None
    
    def resolve_email_queue(self, info, **kwargs):
        """Resolver for the GraphQL field `email queue`."""
        return EmailQueue.objects.filter(status='pending')
    
    def resolve_my_push_notifications(self, info):
        """Resolver for the GraphQL field `my push notifications`."""
        user = info.context.user
        if user.is_anonymous:
            raise Exception('Not logged in!')
        return PushNotification.objects.filter(user=user)


# Mutations
class CreateNotificationMutation(graphene.Mutation):
    """Create a notification for a user"""
    class Arguments:
        """Defines the purpose and behavior of the `Arguments` class."""
        user_id = graphene.ID(required=True)
        type = graphene.String(required=True)
        title = graphene.String(required=True)
        message = graphene.String(required=True)
        priority = graphene.String()
        link = graphene.String()
        data = graphene.JSONString()
    
    notification = graphene.Field(NotificationType)
    
    @classmethod
    def mutate(cls, root, info, user_id, type, title, message, **kwargs):
        """Executes mutation business rules and returns the mutation response object."""
        from user_service.models import User
        
        try:
            user = User.objects.get(pk=int(user_id))
        except (User.DoesNotExist, ValueError):
            raise Exception('User not found')
        
        notification = Notification.objects.create(
            user=user,
            type=type,
            title=title,
            message=message,
            priority=kwargs.get('priority', 'normal'),
            link=kwargs.get('link', ''),
            data=kwargs.get('data', {})
        )
        
        return CreateNotificationMutation(notification=notification)


class MarkNotificationReadMutation(graphene.Mutation):
    """Mark a notification as read"""
    class Arguments:
        """Defines the purpose and behavior of the `Arguments` class."""
        notification_id = graphene.ID(required=True)
    
    notification = graphene.Field(NotificationType)
    
    @classmethod
    def mutate(cls, root, info, notification_id):
        """Executes mutation business rules and returns the mutation response object."""
        user = info.context.user
        if user.is_anonymous:
            raise Exception('Not logged in!')
        
        try:
            notification = Notification.objects.get(
                pk=int(notification_id),
                user=user
            )
            notification.is_read = True
            notification.read_at = datetime.now()
            notification.save()
            return MarkNotificationReadMutation(notification=notification)
        except (Notification.DoesNotExist, ValueError):
            raise Exception('Notification not found')


class MarkAllNotificationsReadMutation(graphene.Mutation):
    """Mark all notifications as read"""
    
    class Arguments:
        """Defines the purpose and behavior of the `Arguments` class."""
        pass
    
    success = graphene.Boolean()
    
    @classmethod
    def mutate(cls, root, info):
        """Executes mutation business rules and returns the mutation response object."""
        user = info.context.user
        if user.is_anonymous:
            raise Exception('Not logged in!')
        
        Notification.objects.filter(user=user, is_read=False).update(
            is_read=True,
            read_at=datetime.now()
        )
        
        return MarkAllNotificationsReadMutation(success=True)


class DeleteNotificationMutation(graphene.Mutation):
    """Delete a notification"""
    class Arguments:
        """Defines the purpose and behavior of the `Arguments` class."""
        notification_id = graphene.ID(required=True)
    
    success = graphene.Boolean()
    
    @classmethod
    def mutate(cls, root, info, notification_id):
        """Executes mutation business rules and returns the mutation response object."""
        user = info.context.user
        if user.is_anonymous:
            raise Exception('Not logged in!')
        
        try:
            notification = Notification.objects.get(
                pk=int(notification_id),
                user=user
            )
            notification.delete()
            return DeleteNotificationMutation(success=True)
        except (Notification.DoesNotExist, ValueError):
            return DeleteNotificationMutation(success=False)


class CreateEmailTemplateMutation(graphene.Mutation):
    """Create an email template"""
    class Arguments:
        """Defines the purpose and behavior of the `Arguments` class."""
        name = graphene.String(required=True)
        subject = graphene.String(required=True)
        body = graphene.String(required=True)
        type = graphene.String(required=True)
    
    email_template = graphene.Field(EmailTemplateType)
    
    @classmethod
    def mutate(cls, root, info, name, subject, body, type):
        """Executes mutation business rules and returns the mutation response object."""
        template = EmailTemplate.objects.create(
            name=name,
            subject=subject,
            body=body,
            type=type
        )
        
        return CreateEmailTemplateMutation(email_template=template)


class QueueEmailMutation(graphene.Mutation):
    """Queue an email for sending"""
    class Arguments:
        """Defines the purpose and behavior of the `Arguments` class."""
        to_email = graphene.String(required=True)
        subject = graphene.String(required=True)
        body = graphene.String(required=True)
    
    email = graphene.Field(EmailQueueType)
    
    @classmethod
    def mutate(cls, root, info, to_email, subject, body):
        """Executes mutation business rules and returns the mutation response object."""
        email = EmailQueue.objects.create(
            to_email=to_email,
            subject=subject,
            body=body
        )
        
        return QueueEmailMutation(email=email)


class SendPushNotificationMutation(graphene.Mutation):
    """Send a push notification"""
    class Arguments:
        """Defines the purpose and behavior of the `Arguments` class."""
        user_id = graphene.ID(required=True)
        title = graphene.String(required=True)
        message = graphene.String(required=True)
        data = graphene.JSONString()
    
    push_notification = graphene.Field(PushNotificationType)
    
    @classmethod
    def mutate(cls, root, info, user_id, title, message, **kwargs):
        """Executes mutation business rules and returns the mutation response object."""
        from user_service.models import User
        
        try:
            user = User.objects.get(pk=int(user_id))
        except (User.DoesNotExist, ValueError):
            raise Exception('User not found')
        
        push_notification = PushNotification.objects.create(
            user=user,
            title=title,
            message=message,
            data=kwargs.get('data', {}),
            is_sent=True,
            sent_at=datetime.now()
        )
        
        return SendPushNotificationMutation(push_notification=push_notification)


class Mutation(graphene.ObjectType):
    """Notification Service Mutations"""
    
    create_notification = CreateNotificationMutation.Field()
    mark_notification_read = MarkNotificationReadMutation.Field()
    mark_all_notifications_read = MarkAllNotificationsReadMutation.Field()
    delete_notification = DeleteNotificationMutation.Field()
    create_email_template = CreateEmailTemplateMutation.Field()
    queue_email = QueueEmailMutation.Field()
    send_push_notification = SendPushNotificationMutation.Field()


# Schema definition for Notification Service


# NOTE: The gateway composes service Query/Mutation classes directly.
# Avoid eager schema instantiation here to prevent duplicate type
# registrations when all services are imported together.
