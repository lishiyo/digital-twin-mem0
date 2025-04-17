from setuptools import find_packages, setup

with open("README.md", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="digital-twin-dao",
    version="0.1.0",
    author="Digital Twin Team",
    author_email="team@digitaltwin.example.com",
    description="Digital Twin & DAO Coordination Backend",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/digital-twin-dao",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.12",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.12",
    install_requires=[
        "fastapi>=0.103.0",
        "uvicorn>=0.23.0",
        "pydantic>=2.3.0",
        "sqlalchemy>=2.0.0",
        "alembic>=1.11.0",
        "psycopg2-binary>=2.9.0",
        "celery>=5.3.0",
        "redis>=4.6.0",
        "openai>=1.0.0",
        "langgraph>=0.3.0",
        "tiktoken>=0.4.0",
        "python-multipart>=0.0.6",
        "tweepy>=4.14.0",
        "telethon>=1.29.0",
        "pdfminer.six>=20221105",
        "httpx>=0.24.1",
        "python-jose[cryptography]>=3.3.0",
        "mem0ai>=0.1.0",  # Replace with actual version
    ],
    extras_require={
        "dev": [
            "pytest>=7.3.1",
            "pytest-asyncio",
            "pytest-cov>=4.1.0",
            "black>=23.7.0",
            "ruff>=0.0.280",
            "mypy>=1.5.1",
            "pre-commit>=3.3.3",
            "types-redis>=4.6.0.3",
            "types-requests>=2.31.0.2",
        ],
    },
)
