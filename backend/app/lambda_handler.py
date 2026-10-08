"""AWS Lambda entry point: API Gateway (HTTP API, payload v2) -> Mangum -> the same FastAPI app used locally."""
from mangum import Mangum

from .main import create_app

app = create_app()
handler = Mangum(app, lifespan="off")  # state is built eagerly in create_app (cold start), so no lifespan hooks are needed
