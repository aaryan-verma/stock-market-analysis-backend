from sqlalchemy.pool import QueuePool

engine = create_engine(
    SQLALCHEMY_DATABASE_URI,
    poolclass=QueuePool,
    pool_size=5,  # Reduce pool size
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800
) 