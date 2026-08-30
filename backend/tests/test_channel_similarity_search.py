from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.bot import CHUNK_EMBEDDING_DIMENSION, embed_question, search_channel_chunks
from app.db import Base
from app.models import Channel, Chunk, File, Membership, Role, User, Workspace


def test_search_channel_chunks_filters_to_channel_and_ranks_by_similarity() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    question = "When is the release date?"
    query_vector = embed_question(question)

    with session_factory() as session:
        user = User(id=uuid4(), email="owner@example.com", password_hash="hash")
        session.add(user)
        workspace = Workspace(id=uuid4(), name="Alpha", owner_id=user.id)
        session.add(workspace)
        channel_a = Channel(id=uuid4(), workspace_id=workspace.id, name="A")
        channel_b = Channel(id=uuid4(), workspace_id=workspace.id, name="B")
        session.add_all([channel_a, channel_b])
        session.add(Membership(id=uuid4(), user_id=user.id, channel_id=channel_a.id, role=Role.OWNER.value))
        session.add(Membership(id=uuid4(), user_id=user.id, channel_id=channel_b.id, role=Role.OWNER.value))

        file_a = File(id=uuid4(), channel_id=channel_a.id, filename="a.pdf", storage_path="a.pdf", uploaded_by=user.id, ingestion_status="completed")
        file_b = File(id=uuid4(), channel_id=channel_b.id, filename="b.pdf", storage_path="b.pdf", uploaded_by=user.id, ingestion_status="completed")
        session.add_all([file_a, file_b])

        same_channel_chunk = Chunk(
            id=uuid4(),
            file_id=file_a.id,
            channel_id=channel_a.id,
            page_number=2,
            section="Overview",
            content="The release date is 2027-01-15.",
            embedding=[0.0] * CHUNK_EMBEDDING_DIMENSION,
        )
        other_channel_chunk = Chunk(
            id=uuid4(),
            file_id=file_b.id,
            channel_id=channel_b.id,
            page_number=5,
            section="Other",
            content="Completely unrelated.",
            embedding=query_vector,
        )
        session.add_all([same_channel_chunk, other_channel_chunk])
        session.commit()

        results = search_channel_chunks(
            db=session,
            channel_id=channel_a.id,
            question=question,
            limit=5,
        )

        assert [chunk.id for chunk in results] == [same_channel_chunk.id]
        assert all(chunk.channel_id == channel_a.id for chunk in results)
        assert all(chunk.id != other_channel_chunk.id for chunk in results)
