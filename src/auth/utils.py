import random
from sqlmodel import select
from src.db.models import Otp

async def invalidate_previous_otps(user, session):
    statement = select(Otp).where(Otp.user_id == user.id)
    results = await session.exec(statement)
    for otp in results.all():
        await session.delete(otp)
    await session.commit()


async def generate_otp(user, session):
    otp_value = random.randint(100000, 999999)
    # Save the OTP to the Otp model
    otp = Otp(user_id=user.id, otp=otp_value)  # type: ignore
    session.add(otp)
    await session.commit()
    await session.refresh(otp)
    return otp.otp