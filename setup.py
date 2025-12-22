"""Setup script for Synaptiq Data Engine."""

from setuptools import setup, find_packages

setup(
    name="synaptiq",
    version="0.1.0",
    description="A production-grade data processing pipeline for personal knowledge management",
    author="Synaptiq Team",
    python_requires=">=3.10",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    install_requires=[
        "fastapi>=0.109.0",
        "uvicorn[standard]>=0.27.0",
        "pydantic>=2.6.0",
        "pydantic-settings>=2.1.0",
        "supadata>=1.0.0",
        "openai>=1.12.0",
        "qdrant-client>=1.7.0",
        "motor>=3.3.0",
        "pymongo>=4.6.0",
        "celery[redis]>=5.3.0",
        "redis>=5.0.0",
        "click>=8.1.0",
        "rich>=13.7.0",
        "python-dotenv>=1.0.0",
        "httpx>=0.26.0",
        "tiktoken>=0.6.0",
        "tenacity>=8.2.0",
        "structlog>=24.1.0",
    ],
    entry_points={
        "console_scripts": [
            "synaptiq=synaptiq.cli.commands:cli",
        ],
    },
)


