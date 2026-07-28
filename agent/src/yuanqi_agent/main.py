import uvicorn

from yuanqi_agent.api import create_app

app = create_app()


def run() -> None:
    uvicorn.run("yuanqi_agent.main:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    run()
