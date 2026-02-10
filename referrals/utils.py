import logging
from django.db import transaction
from decimal import Decimal
import qrcode
import io
import base64

logger = logging.getLogger(__name__)

def process_referral_on_deposit(referred_user, deposit_amount):
    """
    Process referral when referred user makes a deposit
    """
    try:
        with transaction.atomic():
            # Check if user was referred
            try:
                referral = referred_user.referred_by
            except:
                # User was not referred
                return False
            
            # Get referral settings
            from .models import ReferralBonusSettings
            settings = ReferralBonusSettings.get_settings()
            
            # Check if deposit meets minimum requirement
            if deposit_amount < settings.minimum_deposit_for_bonus:
                logger.info(f"Deposit amount ${deposit_amount} does not meet minimum for referral bonus")
                return False
            
            # Update referral
            referral.referred_user_deposited = True
            referral.referred_user_deposit_amount = deposit_amount
            referral.status = referral.ReferralStatus.EARNED
            referral.save()
            
            # Credit bonus to referrer's bonus wallet
            from .models import BonusWallet
            bonus_wallet, created = BonusWallet.objects.get_or_create(
                user=referral.referrer
            )
            
            bonus_wallet.credit(referral.bonus_amount, referral)
            
            # Update referrer's referral code stats
            try:
                from .models import UserReferralCode
                referrer_code = UserReferralCode.objects.get(user=referral.referrer)
                referrer_code.total_referrals += 1
                referrer_code.active_referrals = referrer_code.user.referrals_made.filter(
                    status='PENDING'
                ).count()
                referrer_code.total_bonus_earned += referral.bonus_amount
                referrer_code.save()
            except UserReferralCode.DoesNotExist:
                pass
            
            # Create notification for referrer
            try:
                from notifications.utils import create_notification
                create_notification(
                    user=referral.referrer,
                    notification_type='REFERRAL_BONUS',
                    title='Referral Bonus Earned!',
                    message=f'You earned ${referral.bonus_amount} referral bonus! {referred_user.email} made a deposit of ${deposit_amount}.',
                    metadata={
                        'referred_user': referred_user.email,
                        'deposit_amount': str(deposit_amount),
                        'bonus_amount': str(referral.bonus_amount)
                    }
                )
            except ImportError:
                logger.warning("Notifications app not installed")
            
            logger.info(f"Referral bonus processed: {referral.referrer.email} → {referred_user.email}")
            return True
            
    except Exception as e:
        logger.error(f"Error processing referral bonus: {str(e)}")
        return False


def generate_referral_qr_code(referral_link):
    """
    Generate QR code for referral link
    """
    try:
        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(referral_link)
        qr.make(fit=True)
        
        # Create image
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to base64
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        img_str = base64.b64encode(buffer.getvalue()).decode()
        
        # Return data URL
        return f"data:image/png;base64,{img_str}"
        
    except Exception as e:
        logger.error(f"Error generating QR code: {str(e)}")
        return None


def create_referral(referrer, referred_user):
    """
    Create a new referral relationship
    """
    try:
        from .models import Referral, ReferralBonusSettings, UserReferralCode
        
        # Get settings
        settings = ReferralBonusSettings.get_settings()
        
        # Get referrer's code
        referrer_code, created = UserReferralCode.objects.get_or_create(user=referrer)
        if created:
            referrer_code.generate_code()
            referrer_code.save()
        
        # Create referral
        referral = Referral.objects.create(
            referrer=referrer,
            referred_user=referred_user,
            referral_code=referrer_code.get_display_code(),
            bonus_amount=settings.default_bonus_amount,
            status=Referral.ReferralStatus.PENDING
        )
        
        # Update referrer's stats
        referrer_code.total_referrals += 1
        referrer_code.active_referrals += 1
        referrer_code.save()
        
        # Create bonus wallet for referrer if not exists
        from .models import BonusWallet
        BonusWallet.objects.get_or_create(user=referrer)
        
        logger.info(f"Referral created: {referrer.email} → {referred_user.email}")
        return referral
        
    except Exception as e:
        logger.error(f"Error creating referral: {str(e)}")
        return None

