# Regex concept:
# Look for '@' that is NOT preceded by an alphanumeric character (to avoid emails).
# Followed by valid username characters: [a-zA-Z0-9_.-]

from re import findall
import string
from uuid import UUID
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import User,Membership

PATTERN = r"(?<!\w)@([a-zA-Z0-9_.-]+)"

def extract_mention_usernames(content: str) -> set[str]:
    """
    Extracts unique usernames from a string.
    """
    # 1. Find all regex matches
    raw_matches = findall(PATTERN, content)
    
    # 2. Clean each match
    candidates: set[str] = set()
    for match in raw_matches:
        # Strip trailing punctuation like '.', ',', '!', '?'
        PUNCTUATION_TO_STRIP = string.punctuation.replace("_", "")
        clean_name = match.rstrip(PUNCTUATION_TO_STRIP)
        if clean_name:
            # Normalize to lowercase
            candidates.add(clean_name.lower())
            
    return candidates

async def resolve_channel_mentions(
    db:AsyncSession,
    channel_id:UUID,
    sender_id:UUID,
    candidate_usernames:set[str]
):
    if not candidate_usernames:
        return {}
    stmt =(
        select(User.id,User.username,)
        .join(Membership,Membership.user_id == User.id)
        .where(
            Membership.channel_id == channel_id,
            Membership.user_id != sender_id,
            func.lower(User.username).in_(candidate_usernames),

        )
    )

    result = await db.execute(stmt)
    return {row[1]: row[0] for row in result.all()}
    