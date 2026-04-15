import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


async def authenticate_user(
    session: AsyncSession, username: str, password: str
) -> User | None:
    result = await session.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user and verify_password(password, user.password_hash):
        return user
    return None


async def create_default_admin(session: AsyncSession) -> None:
    result = await session.execute(select(User).where(User.username == "admin"))
    if result.scalar_one_or_none():
        return
    admin = User(
        username="admin",
        display_name="Administrator",
        password_hash=hash_password("admin"),
        role="superadmin",
    )
    session.add(admin)
    await session.commit()
