"""
OTP Authentication GraphQL Schema
GraphQL API for OTP-based authentication and address management
"""
import graphene
from graphene import relay
from graphene_django import DjangoObjectType
from django.contrib.auth.models import User
from django.utils import timezone
from .auth_models import OTPVerification, DeliveryAddress, OTPLog
from django.db.models import Q
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


class AuthUserType(DjangoObjectType):
    """GraphQL type for User (for auth mutations)"""
    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name"]


class OTPVerificationType(DjangoObjectType):
    """GraphQL type for OTP Verification"""
    is_expired = graphene.Boolean()
    
    class Meta:
        model = OTPVerification
        fields = ['id', 'phone_number', 'status', 'created_at', 'expires_at']
        interfaces = (relay.Node,)
    
    def resolve_is_expired(self, info):
        return self.is_expired()


class DeliveryAddressType(DjangoObjectType):
    """GraphQL type for Delivery Address"""
    full_address = graphene.String()
    
    class Meta:
        model = DeliveryAddress
        fields = [
            'id', 'full_name', 'phone_number', 'address_line1', 'address_line2',
            'city', 'state', 'postal_code', 'country', 'address_type',
            'is_default', 'created_at', 'updated_at'
        ]
        interfaces = (relay.Node,)
    
    def resolve_full_address(self, info):
        return self.get_full_address()


class SendOTPMutation(graphene.Mutation):
    """Send OTP to phone number"""
    success = graphene.Boolean()
    message = graphene.String()
    otp_id = graphene.Int()
    expires_in = graphene.Int()  # seconds
    
    class Arguments:
        phone_number = graphene.String(required=True)
    
    def mutate(self, info, phone_number):
        try:
            # Validate phone number format
            if not phone_number or len(phone_number) < 10:
                return SendOTPMutation(
                    success=False,
                    message="Invalid phone number format"
                )
            
            # Check if phone already has an active OTP
            existing_otp = OTPVerification.objects.filter(
                phone_number=phone_number,
                status=OTPVerification.OTPStatus.PENDING,
                expires_at__gt=timezone.now()
            ).first()
            
            if existing_otp:
                # Return existing OTP if still valid
                expires_in = int((existing_otp.expires_at - timezone.now()).total_seconds())
                
                # Log the attempt
                OTPLog.objects.create(
                    phone_number=phone_number,
                    action=OTPLog.OTPAction.SENT,
                    otp=existing_otp,
                    ip_address=info.context.META.get('REMOTE_ADDR'),
                )
                
                return SendOTPMutation(
                    success=True,
                    message="OTP resent to your phone",
                    otp_id=existing_otp.id,
                    expires_in=expires_in
                )
            
            # Create new OTP
            otp = OTPVerification.create_otp(phone_number, expires_in_minutes=10)
            
            # Log the OTP creation
            OTPLog.objects.create(
                phone_number=phone_number,
                action=OTPLog.OTPAction.SENT,
                otp=otp,
                ip_address=info.context.META.get('REMOTE_ADDR'),
            )
            
            # TODO: Actually send OTP via SMS
            # For now, log it for development
            print(f"📱 OTP for {phone_number}: {otp.otp_code}")
            
            expires_in = int((otp.expires_at - timezone.now()).total_seconds())
            
            return SendOTPMutation(
                success=True,
                message=f"OTP sent to {phone_number}. Valid for 10 minutes.",
                otp_id=otp.id,
                expires_in=expires_in
            )
        
        except Exception as e:
            return SendOTPMutation(
                success=False,
                message=f"Error sending OTP: {str(e)}"
            )


class VerifyOTPMutation(graphene.Mutation):
    """Verify OTP and return authentication token"""
    success = graphene.Boolean()
    message = graphene.String()
    token = graphene.String()
    user = graphene.Field(AuthUserType)  # User type
    
    class Arguments:
        phone_number = graphene.String(required=True)
        otp_code = graphene.String(required=True)
    
    def mutate(self, info, phone_number, otp_code):
        try:
            # Find the OTP
            otp = OTPVerification.objects.filter(
                phone_number=phone_number,
                status=OTPVerification.OTPStatus.PENDING
            ).first()
            
            if not otp:
                return VerifyOTPMutation(
                    success=False,
                    message="No pending OTP found for this phone number"
                )
            
            # Verify the OTP
            if not otp.verify(otp_code):
                # Log failed attempt
                OTPLog.objects.create(
                    phone_number=phone_number,
                    action=OTPLog.OTPAction.FAILED,
                    otp=otp,
                    ip_address=info.context.META.get('REMOTE_ADDR'),
                )
                
                remaining_attempts = otp.max_attempts - otp.attempts
                return VerifyOTPMutation(
                    success=False,
                    message=f"Invalid OTP. {remaining_attempts} attempts remaining."
                )
            
            # Find or create user
            try:
                user = User.objects.get(username=phone_number)
            except User.DoesNotExist:
                # Create new user with phone as username
                user = User.objects.create_user(
                    username=phone_number,
                    phone=phone_number,
                    is_active=True
                )
            
            # Log successful verification
            OTPLog.objects.create(
                phone_number=phone_number,
                action=OTPLog.OTPAction.VERIFIED,
                otp=otp,
                ip_address=info.context.META.get('REMOTE_ADDR'),
            )
            
            # TODO: Generate JWT token or session token
            # For now, return a simple token
            token = f"token_{user.id}_{timezone.now().timestamp()}"
            
            return VerifyOTPMutation(
                success=True,
                message="OTP verified successfully",
                token=token,
                user=user
            )
        
        except Exception as e:
            return VerifyOTPMutation(
                success=False,
                message=f"Error verifying OTP: {str(e)}"
            )


class RegisterCustomerMutation(graphene.Mutation):
    """Complete customer registration"""
    success = graphene.Boolean()
    message = graphene.String()
    token = graphene.String()
    user = graphene.Field(AuthUserType)
    
    class Arguments:
        phone_number = graphene.String(required=True)
        otp_code = graphene.String(required=True)
        first_name = graphene.String(required=True)
        last_name = graphene.String(required=True)
        email = graphene.String(required=False)
    
    def mutate(self, info, phone_number, otp_code, first_name, last_name, email=None):
        try:
            # Verify OTP first
            otp = OTPVerification.objects.filter(
                phone_number=phone_number,
                status=OTPVerification.OTPStatus.VERIFIED,
                is_used=False
            ).first()
            
            if not otp:
                return RegisterCustomerMutation(
                    success=False,
                    message="Invalid or unverified OTP"
                )
            
            # Create or update user
            user, created = User.objects.update_or_create(
                username=phone_number,
                defaults={
                    'first_name': first_name,
                    'last_name': last_name,
                    'email': email or f"{phone_number}@example.com",
                    'phone': phone_number,
                    'is_active': True,
                }
            )
            
            # Mark OTP as used
            otp.is_used = True
            otp.save()
            
            # TODO: Generate JWT token
            token = f"token_{user.id}_{timezone.now().timestamp()}"
            
            return RegisterCustomerMutation(
                success=True,
                message=f"Welcome {first_name}! Registration successful.",
                token=token,
                user=user
            )
        
        except Exception as e:
            return RegisterCustomerMutation(
                success=False,
                message=f"Registration error: {str(e)}"
            )


class AddDeliveryAddressMutation(graphene.Mutation):
    """Add a new delivery address"""
    success = graphene.Boolean()
    message = graphene.String()
    address = graphene.Field(DeliveryAddressType)
    
    class Arguments:
        full_name = graphene.String(required=True)
        phone_number = graphene.String(required=True)
        address_line1 = graphene.String(required=True)
        address_line2 = graphene.String()
        city = graphene.String(required=True)
        state = graphene.String(required=True)
        postal_code = graphene.String(required=True)
        country = graphene.String(required=True)
        address_type = graphene.String(required=False, default_value='home')
        is_default = graphene.Boolean(required=False, default_value=False)
    
    def mutate(self, info, full_name, phone_number, address_line1, city, state,
               postal_code, country, address_type='home', is_default=False,
               address_line2=''):
        try:
            user = info.context.user
            if not user.is_authenticated:
                return AddDeliveryAddressMutation(
                    success=False,
                    message="User not authenticated"
                )
            
            address = DeliveryAddress.objects.create(
                user=user,
                full_name=full_name,
                phone_number=phone_number,
                address_line1=address_line1,
                address_line2=address_line2,
                city=city,
                state=state,
                postal_code=postal_code,
                country=country,
                address_type=address_type,
                is_default=is_default
            )
            
            return AddDeliveryAddressMutation(
                success=True,
                message="Address added successfully",
                address=address
            )
        
        except Exception as e:
            return AddDeliveryAddressMutation(
                success=False,
                message=f"Error adding address: {str(e)}"
            )


class UpdateDeliveryAddressMutation(graphene.Mutation):
    """Update delivery address"""
    success = graphene.Boolean()
    message = graphene.String()
    address = graphene.Field(DeliveryAddressType)
    
    class Arguments:
        address_id = graphene.Int(required=True)
        full_name = graphene.String()
        phone_number = graphene.String()
        address_line1 = graphene.String()
        address_line2 = graphene.String()
        city = graphene.String()
        state = graphene.String()
        postal_code = graphene.String()
        country = graphene.String()
        is_default = graphene.Boolean()
    
    def mutate(self, info, address_id, **kwargs):
        try:
            user = info.context.user
            if not user.is_authenticated:
                return UpdateDeliveryAddressMutation(
                    success=False,
                    message="User not authenticated"
                )
            
            address = DeliveryAddress.objects.get(id=address_id, user=user)
            
            for key, value in kwargs.items():
                if value is not None:
                    setattr(address, key, value)
            
            address.save()
            
            return UpdateDeliveryAddressMutation(
                success=True,
                message="Address updated successfully",
                address=address
            )
        
        except DeliveryAddress.DoesNotExist:
            return UpdateDeliveryAddressMutation(
                success=False,
                message="Address not found"
            )
        except Exception as e:
            return UpdateDeliveryAddressMutation(
                success=False,
                message=f"Error updating address: {str(e)}"
            )


class DeleteDeliveryAddressMutation(graphene.Mutation):
    """Delete delivery address"""
    success = graphene.Boolean()
    message = graphene.String()
    
    class Arguments:
        address_id = graphene.Int(required=True)
    
    def mutate(self, info, address_id):
        try:
            user = info.context.user
            if not user.is_authenticated:
                return DeleteDeliveryAddressMutation(
                    success=False,
                    message="User not authenticated"
                )
            
            address = DeliveryAddress.objects.get(id=address_id, user=user)
            address.delete()
            
            return DeleteDeliveryAddressMutation(
                success=True,
                message="Address deleted successfully"
            )
        
        except DeliveryAddress.DoesNotExist:
            return DeleteDeliveryAddressMutation(
                success=False,
                message="Address not found"
            )
        except Exception as e:
            return DeleteDeliveryAddressMutation(
                success=False,
                message=f"Error deleting address: {str(e)}"
            )


class SetDefaultAddressMutation(graphene.Mutation):
    """Set default delivery address"""
    success = graphene.Boolean()
    message = graphene.String()
    address = graphene.Field(DeliveryAddressType)
    
    class Arguments:
        address_id = graphene.Int(required=True)
    
    def mutate(self, info, address_id):
        try:
            user = info.context.user
            if not user.is_authenticated:
                return SetDefaultAddressMutation(
                    success=False,
                    message="User not authenticated"
                )
            
            address = DeliveryAddress.objects.get(id=address_id, user=user)
            address.is_default = True
            address.save()
            
            return SetDefaultAddressMutation(
                success=True,
                message="Default address updated",
                address=address
            )
        
        except DeliveryAddress.DoesNotExist:
            return SetDefaultAddressMutation(
                success=False,
                message="Address not found"
            )
        except Exception as e:
            return SetDefaultAddressMutation(
                success=False,
                message=f"Error setting default address: {str(e)}"
            )


class AuthQuery(graphene.ObjectType):
    """Authentication queries"""
    get_delivery_addresses = graphene.List(DeliveryAddressType)
    get_default_address = graphene.Field(DeliveryAddressType)
    
    def resolve_get_delivery_addresses(self, info):
        user = info.context.user
        if not user.is_authenticated:
            return []
        return user.user_delivery_addresses.filter(is_active=True)
    
    def resolve_get_default_address(self, info):
        user = info.context.user
        if not user.is_authenticated:
            return None
        return user.user_delivery_addresses.filter(
            is_active=True,
            is_default=True
        ).first()


class AuthMutation(graphene.ObjectType):
    """Authentication mutations"""
    send_otp = SendOTPMutation.Field()
    verify_otp = VerifyOTPMutation.Field()
    register_customer = RegisterCustomerMutation.Field()
    add_delivery_address = AddDeliveryAddressMutation.Field()
    update_delivery_address = UpdateDeliveryAddressMutation.Field()
    delete_delivery_address = DeleteDeliveryAddressMutation.Field()
    set_default_address = SetDefaultAddressMutation.Field()
