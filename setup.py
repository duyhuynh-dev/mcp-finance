from setuptools import setup

setup(
    name="finance-stack",
    version="0.1.0",
    packages=["finance_core"],
    package_dir={"finance_core": "packages/core/finance_core"},
    python_requires=">=3.11",
    install_requires=[
        "mcp>=1.2.0",
        "fastapi>=0.115.0",
        "uvicorn[standard]>=0.32.0",
        "pydantic>=2.10.0",
        "pydantic-settings>=2.6.0",
        "httpx>=0.27.0",
    ],
    extras_require={
        "dev": [
            "pytest>=8.0.0",
            "ruff>=0.8.0",
        ],
    },
)
