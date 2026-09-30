class AsyncSessionAdapter:
    """AsyncSession-shaped adapter for the existing in-memory test database."""

    def __init__(self, session):
        self._session = session

    def add(self, instance):
        self._session.add(instance)

    def add_all(self, instances):
        self._session.add_all(instances)

    async def scalar(self, statement):
        return self._session.scalar(statement)

    async def scalars(self, statement):
        return self._session.scalars(statement)

    async def execute(self, statement):
        return self._session.execute(statement)

    async def get(self, model, identity):
        return self._session.get(model, identity)

    async def commit(self):
        self._session.commit()

    async def rollback(self):
        self._session.rollback()

    async def flush(self):
        self._session.flush()

    async def refresh(self, instance):
        self._session.refresh(instance)

    async def delete(self, instance):
        self._session.delete(instance)
