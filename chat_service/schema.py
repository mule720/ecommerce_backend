"""
Chat Service GraphQL Schema - Live chat support
"""

import graphene
from graphene_django import DjangoObjectType
from graphene_django.filter import DjangoFilterConnectionField
from django.db.models import Q, Count
from django.utils import timezone
from django.contrib.auth import get_user_model

from chat_service.models import (
    ChatRoom,
    ChatMessage,
    ChatTemplate,
    ChatQueue,
    ChatRating,
    ChatBan
)

User = get_user_model()


# ============= ObjectTypes =============

class ChatRoomType(DjangoObjectType):
    """Chat room GraphQL type"""
    
    customer_name = graphene.String()
    agent_name = graphene.String()
    last_message = graphene.String()
    unread_count = graphene.Int()
    duration_minutes = graphene.Int()
    
    class Meta:
        """Defines the purpose and behavior of the `Meta` class."""
        model = ChatRoom
        fields = [
            'id', 'customer', 'assigned_agent', 'product', 'order',
            'status', 'priority', 'subject', 'message_count',
            'first_response_time', 'resolution_time',
            'satisfaction_rating', 'feedback', 'created_at', 'updated_at', 'closed_at'
        ]
    
    def resolve_customer_name(self, info):
        """Resolver for the GraphQL field `customer name`."""
        return self.customer.get_full_name() or self.customer.username
    
    def resolve_agent_name(self, info):
        """Resolver for the GraphQL field `agent name`."""
        if self.assigned_agent:
            return self.assigned_agent.get_full_name() or self.assigned_agent.username
        return None
    
    def resolve_last_message(self, info):
        """Resolver for the GraphQL field `last message`."""
        last_msg = self.messages.order_by('-created_at').first()
        return last_msg.content if last_msg else None
    
    def resolve_unread_count(self, info):
        """Resolver for the GraphQL field `unread count`."""
        user = info.context.user
        if user.is_authenticated:
            return self.messages.filter(is_read=False).exclude(sender=user).count()
        return 0
    
    def resolve_duration_minutes(self, info):
        """Resolver for the GraphQL field `duration minutes`."""
        end = self.closed_at or timezone.now()
        duration = end - self.created_at
        return int(duration.total_seconds() / 60)


class ChatMessageType(DjangoObjectType):
    """Chat message GraphQL type"""
    
    sender_name = graphene.String()
    sender_role = graphene.String()
    
    class Meta:
        """Defines the purpose and behavior of the `Meta` class."""
        model = ChatMessage
        fields = [
            'id', 'room', 'sender', 'message_type', 'content',
            'file_url', 'file_name', 'file_size', 'is_read',
            'read_at', 'created_at', 'updated_at'
        ]
    
    def resolve_sender_name(self, info):
        """Resolver for the GraphQL field `sender name`."""
        if self.sender:
            return self.sender.get_full_name() or self.sender.username
        return "System"
    
    def resolve_sender_role(self, info):
        """Resolver for the GraphQL field `sender role`."""
        if self.sender:
            if hasattr(self.sender, 'profile') and self.sender.profile.is_agent:
                return 'agent'
            if self.sender.is_staff:
                return 'staff'
        return 'customer'


class ChatTemplateType(DjangoObjectType):
    """Canned response templates"""
    
    class Meta:
        """Defines the purpose and behavior of the `Meta` class."""
        model = ChatTemplate
        fields = [
            'id', 'category', 'title', 'content', 'shortcuts',
            'usage_count', 'is_active', 'created_by', 'created_at'
        ]


class ChatQueueType(DjangoObjectType):
    """Chat queue status"""
    
    queue_length = graphene.Int()
    
    class Meta:
        """Defines the purpose and behavior of the `Meta` class."""
        model = ChatQueue
        fields = [
            'id', 'room', 'queue_type', 'position',
            'estimated_wait_time', 'created_at', 'assigned_at'
        ]
    
    def resolve_queue_length(self, info):
        """Resolver for the GraphQL field `queue length`."""
        return ChatQueue.objects.filter(
            queue_type=self.queue_type,
            assigned_at__isnull=True
        ).count()


class ChatRatingType(DjangoObjectType):
    """Satisfaction rating"""
    
    class Meta:
        """Defines the purpose and behavior of the `Meta` class."""
        model = ChatRating
        fields = [
            'id', 'room', 'rating', 'comment',
            'resolved', 'helpful', 'created_at'
        ]


class ChatStatisticsType(graphene.ObjectType):
    """Chat room statistics"""
    
    total_chats = graphene.Int()
    active_chats = graphene.Int()
    avg_resolution_time = graphene.Float()
    avg_satisfaction_rating = graphene.Float()
    first_response_time_avg = graphene.Float()
    total_messages = graphene.Int()
    messages_per_chat = graphene.Float()


class AvailableAgentType(graphene.ObjectType):
    """Available support agent summary"""
    id = graphene.ID()
    name = graphene.String()
    active_chats = graphene.Int()


class ChatQuery(graphene.ObjectType):
    """Chat room queries"""
    
    # Get user's chat rooms
    my_chats = graphene.List(
        ChatRoomType,
        status=graphene.String(),
        limit=graphene.Int(default_value=20),
        offset=graphene.Int(default_value=0),
        description="Get user's chat rooms"
    )
    
    # Get specific chat room
    chat_room = graphene.Field(
        ChatRoomType,
        id=graphene.ID(required=True),
        description="Get specific chat room details"
    )
    
    # Chat history with messages
    chat_history = graphene.List(
        ChatMessageType,
        room_id=graphene.ID(required=True),
        limit=graphene.Int(default_value=50),
        offset=graphene.Int(default_value=0),
        description="Get chat message history"
    )
    
    # Available support agents
    available_agents = graphene.List(
        AvailableAgentType,
        queue_type=graphene.String(default_value='general'),
        description="Get available support agents"
    )
    
    # Chat templates
    chat_templates = graphene.List(
        ChatTemplateType,
        category=graphene.String(),
        description="Get canned response templates"
    )
    
    # Chat queue status
    queue_status = graphene.Field(
        ChatQueueType,
        room_id=graphene.ID(required=True),
        description="Check chat position in queue"
    )
    
    # Chat statistics (admin/agent only)
    chat_statistics = graphene.Field(
        ChatStatisticsType,
        agent_id=graphene.ID(),
        days=graphene.Int(default_value=30),
        description="Get chat statistics"
    )
    
    def resolve_my_chats(self, info, status=None, limit=20, offset=0, **kwargs):
        """Get user's active and past chat rooms"""
        if not info.context.user.is_authenticated:
            return []
        
        user = info.context.user
        query = ChatRoom.objects.filter(
            Q(customer=user) | Q(assigned_agent=user)
        ).distinct()
        
        if status:
            query = query.filter(status=status)
        
        return query.order_by('-updated_at')[offset:offset + limit]
    
    def resolve_chat_room(self, info, id, **kwargs):
        """Get single chat room with authorization"""
        user = info.context.user
        if not user.is_authenticated:
            return None
        
        try:
            room = ChatRoom.objects.get(id=id)
            # Allow customer, assigned agent, or staff
            if (room.customer == user or room.assigned_agent == user or user.is_staff):
                return room
        except ChatRoom.DoesNotExist:
            pass
        return None
    
    def resolve_chat_history(self, info, room_id, limit=50, offset=0, **kwargs):
        """Get chat messages with authorization"""
        user = info.context.user
        if not user.is_authenticated:
            return []
        
        try:
            room = ChatRoom.objects.get(id=room_id)
            # Verify access
            if room.customer != user and room.assigned_agent != user and not user.is_staff:
                return []
            
            # Mark messages as read for current user
            room.messages.filter(is_read=False).exclude(sender=user).update(
                is_read=True,
                read_at=timezone.now()
            )
            
            return room.messages.all()[offset:offset + limit]
        except ChatRoom.DoesNotExist:
            pass
        return []
    
    def resolve_available_agents(self, info, queue_type='general', **kwargs):
        """Get available agents for queue type"""
        # Simple implementation - can be extended with realistic availability
        from django.contrib.auth.models import Group
        
        agents = User.objects.filter(
            groups__name__in=['support_agent', 'admin']
        ).values('id', 'username', 'first_name', 'last_name').annotate(
            active_chats=Count('chat_rooms_assigned', filter=Q(chat_rooms_assigned__status='active'))
        )
        
        # Return agents with < 5 active chats
        available = [
            AvailableAgentType(
                id=agent['id'],
                name=f"{agent['first_name']} {agent['last_name']}".strip() or agent['username'],
                active_chats=agent['active_chats']
            )
            for agent in agents if agent['active_chats'] < 5
        ]
        return available
    
    def resolve_chat_templates(self, info, category=None, **kwargs):
        """Get canned response templates"""
        query = ChatTemplate.objects.filter(is_active=True)
        if category:
            query = query.filter(category=category)
        return query.order_by('category', 'title')
    
    def resolve_queue_status(self, info, room_id, **kwargs):
        """Check chat queue position"""
        try:
            return ChatQueue.objects.get(room_id=room_id)
        except ChatQueue.DoesNotExist:
            return None
    
    def resolve_chat_statistics(self, info, agent_id=None, days=30, **kwargs):
        """Get chat metrics and KPIs"""
        if not info.context.user.is_staff:
            return None
        
        from datetime import timedelta
        from django.db.models import Avg, Q as DjangoQ, F
        
        since = timezone.now() - timedelta(days=days)
        
        if agent_id:
            rooms = ChatRoom.objects.filter(
                assigned_agent_id=agent_id,
                created_at__gte=since
            )
        else:
            rooms = ChatRoom.objects.filter(created_at__gte=since)
        
        stats = rooms.aggregate(
            total=Count('id'),
            active=Count('id', filter=DjangoQ(status='active')),
            avg_resolution=Avg('resolution_time'),
            avg_satisfaction=Avg('satisfaction_rating'),
            avg_first_response=Avg('first_response_time')
        )
        
        total_messages = ChatMessage.objects.filter(
            room__in=rooms
        ).count()
        
        return ChatStatisticsType(
            total_chats=stats['total'] or 0,
            active_chats=stats['active'] or 0,
            avg_resolution_time=float(stats['avg_resolution'].total_seconds()) if stats['avg_resolution'] else 0,
            avg_satisfaction_rating=float(stats['avg_satisfaction'] or 0),
            first_response_time_avg=float(stats['avg_first_response'].total_seconds()) if stats['avg_first_response'] else 0,
            total_messages=total_messages,
            messages_per_chat=total_messages / (stats['total'] or 1)
        )


class ChatMutation(graphene.ObjectType):
    """Chat operations"""
    
    # Start new chat
    start_chat = graphene.Field(
        ChatRoomType,
        subject=graphene.String(required=True),
        queue_type=graphene.String(default_value='general'),
        product_id=graphene.ID(),
        order_id=graphene.ID(),
        description="Initiate a new chat session"
    )
    
    # Send message
    send_message = graphene.Field(
        ChatMessageType,
        room_id=graphene.ID(required=True),
        content=graphene.String(required=True),
        message_type=graphene.String(default_value='text'),
        file_url=graphene.String(),
        file_name=graphene.String(),
        description="Send message in chat"
    )
    
    # Close chat
    close_chat = graphene.Field(
        ChatRoomType,
        room_id=graphene.ID(required=True),
        description="Close chat room"
    )
    
    # Rate chat (customer)
    rate_chat = graphene.Field(
        ChatRatingType,
        room_id=graphene.ID(required=True),
        rating=graphene.Int(required=True),
        comment=graphene.String(),
        resolved=graphene.Boolean(),
        helpful=graphene.Boolean(),
        description="Rate chat experience"
    )
    
    # Assign agent to chat (staff only)
    assign_agent = graphene.Field(
        ChatRoomType,
        room_id=graphene.ID(required=True),
        agent_id=graphene.ID(required=True),
        description="Assign agent to chat"
    )
    
    # Use template response
    send_template = graphene.Field(
        ChatMessageType,
        room_id=graphene.ID(required=True),
        template_id=graphene.ID(required=True),
        description="Send templated canned response"
    )
    
    def mutate_start_chat(self, info, subject, queue_type='general', product_id=None, order_id=None, **kwargs):
        """Create new chat room"""
        user = info.context.user
        if not user.is_authenticated:
            raise Exception("Must be authenticated to start chat")
        
        # Check if banned
        from chat_service.models import ChatBan
        if ChatBan.objects.filter(user=user, banned_until__gt=timezone.now()).exists():
            raise Exception("User is banned from chat")
        
        # Create room
        room = ChatRoom.objects.create(
            customer=user,
            subject=subject,
            priority='medium',
            status='waiting'
        )
        
        if product_id:
            from product_service.models import Product
            try:
                room.product = Product.objects.get(id=product_id)
            except:
                pass
        
        if order_id:
            from order_service.models import Order
            try:
                room.order = Order.objects.get(id=order_id)
            except:
                pass
        
        room.save()
        
        # Add to queue
        ChatQueue.objects.create(
            room=room,
            queue_type=queue_type,
            position=ChatQueue.objects.filter(queue_type=queue_type, assigned_at__isnull=True).count() + 1
        )
        
        return ChatMutation(start_chat=room)
    
    def mutate_send_message(self, info, room_id, content, message_type='text', file_url=None, file_name=None, **kwargs):
        """Send message in chat"""
        user = info.context.user
        if not user.is_authenticated:
            raise Exception("Must be authenticated to send messages")
        
        try:
            room = ChatRoom.objects.get(id=room_id)
            
            # Verify access
            if room.customer != user and room.assigned_agent != user and not user.is_staff:
                raise Exception("Not authorized to send message in this room")
            
            # Record message
            message = ChatMessage.objects.create(
                room=room,
                sender=user,
                message_type=message_type,
                content=content,
                file_url=file_url or None,
                file_name=file_name or None
            )
            
            # Update room metrics
            room.message_count = ChatMessage.objects.filter(room=room).count()
            room.updated_at = timezone.now()
            room.status = 'active'
            room.save()
            
            return ChatMutation(send_message=message)
        except ChatRoom.DoesNotExist:
            raise Exception("Chat room not found")
    
    def mutate_close_chat(self, info, room_id, **kwargs):
        """Close chat session"""
        user = info.context.user
        if not user.is_authenticated:
            raise Exception("Must be authenticated")
        
        try:
            room = ChatRoom.objects.get(id=room_id)
            
            # Only customer or assigned agent can close
            if room.customer != user and room.assigned_agent != user and not user.is_staff:
                raise Exception("Not authorized to close this room")
            
            room.status = 'closed'
            room.closed_at = timezone.now()
            
            # Calculate resolution time
            if room.assigned_agent:
                room.resolution_time = timezone.now() - room.created_at
            
            room.save()
            
            return ChatMutation(close_chat=room)
        except ChatRoom.DoesNotExist:
            raise Exception("Chat room not found")
    
    def mutate_rate_chat(self, info, room_id, rating, comment=None, resolved=None, helpful=None, **kwargs):
        """Rate chat experience"""
        user = info.context.user
        if not user.is_authenticated:
            raise Exception("Must be authenticated")
        
        try:
            room = ChatRoom.objects.get(id=room_id)
            
            # Only customer can rate
            if room.customer != user:
                raise Exception("Only customer can rate this chat")
            
            if not (1 <= rating <= 5):
                raise Exception("Rating must be between 1 and 5")
            
            chat_rating, created = ChatRating.objects.update_or_create(
                room=room,
                defaults={
                    'rating': rating,
                    'comment': comment or '',
                    'resolved': resolved if resolved is not None else False,
                    'helpful': helpful if helpful is not None else False
                }
            )
            
            # Update room satisfaction
            room.satisfaction_rating = rating
            room.save()
            
            return ChatMutation(rate_chat=chat_rating)
        except ChatRoom.DoesNotExist:
            raise Exception("Chat room not found")
    
    def mutate_assign_agent(self, info, room_id, agent_id, **kwargs):
        """Assign support agent to chat"""
        if not info.context.user.is_staff:
            raise Exception("Only staff can assign agents")
        
        try:
            room = ChatRoom.objects.get(id=room_id)
            agent = User.objects.get(id=agent_id)
            
            room.assigned_agent = agent
            room.status = 'active'
            room.save()
            
            # Update queue
            queue = ChatQueue.objects.filter(room=room).first()
            if queue:
                queue.assigned_at = timezone.now()
                queue.save()
            
            return ChatMutation(assign_agent=room)
        except (ChatRoom.DoesNotExist, User.DoesNotExist):
            raise Exception("Room or agent not found")
    
    def mutate_send_template(self, info, room_id, template_id, **kwargs):
        """Use canned response template"""
        user = info.context.user
        if not user.is_authenticated:
            raise Exception("Must be authenticated")
        
        try:
            room = ChatRoom.objects.get(id=room_id)
            template = ChatTemplate.objects.get(id=template_id)
            
            # Verify access
            if room.assigned_agent != user and not user.is_staff:
                raise Exception("Only assigned agent can send template")
            
            # Send as message
            message = ChatMessage.objects.create(
                room=room,
                sender=user,
                message_type='text',
                content=template.content
            )
            
            # Increment template usage
            template.usage_count += 1
            template.save()
            
            return ChatMutation(send_template=message)
        except (ChatRoom.DoesNotExist, ChatTemplate.DoesNotExist):
            raise Exception("Chat room or template not found")


# NOTE:
# The gateway schema composes ChatQuery/ChatMutation directly.
# Avoid creating a standalone schema at import-time because it can
# trigger duplicate GraphQL type registrations in the unified gateway.
