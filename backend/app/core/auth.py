from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from app.core.config import settings
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        if not settings.CLERK_PEM_PUBLIC_KEY:
            raise credentials_exception

        payload = jwt.decode(token, settings.CLERK_PEM_PUBLIC_KEY, algorithms=["RS256"])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        
        # Check if user exists in DB
        user = await User.find_one(User.clerk_id == user_id)
        if user is None:
            # Auto-create user on first login
            email = payload.get("email", "") # Clerk often puts email in token or needs separate call? standard claims often omit email unless requested
            # Hack: For now, if email missing, use placeholder. Real app should query Clerk API or fix token claims.
            user = User(
                clerk_id=user_id, 
                email=email if email else f"{user_id}@viyugam.ai",
                display_name=payload.get("name", "New User")
            )
            await user.insert()
             
        return user
        
    except JWTError:
        raise credentials_exception
