from fastapi import FastAPI

from app.api import device_router, statistic_router

app = FastAPI()

app.include_router(device_router)
app.include_router(statistic_router)


@app.get("/")
def health_check():
    """
    API health check used by the load balancer.
    """
    return {"statusCode": 200}
