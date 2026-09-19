from setuptools import setup, find_packages

setup(
    name="vigil-mcp",
    version="1.0.0",
    description="Vigil Model Context Protocol (MCP) Server",
    packages=find_packages(),
    install_requires=[
        "mcp>=1.0.0",
        "httpx>=0.27.0",
        "pydantic>=2.0.0",
    ],
    entry_points={
        "console_scripts": [
            "vigil-mcp=vigil_mcp.server:main",
        ],
    },
)
