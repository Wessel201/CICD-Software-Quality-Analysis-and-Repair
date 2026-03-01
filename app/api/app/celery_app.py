import os

from celery import Celery


def create_celery_app() -> Celery:
    broker_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    result_backend = os.getenv("CELERY_RESULT_BACKEND", broker_url)

    celery_application = Celery(
        "code_quality_orchestrator",
        broker=broker_url,
        backend=result_backend,
    )

    task_always_eager = os.getenv("CELERY_TASK_ALWAYS_EAGER", "true").lower() == "true"
    celery_application.conf.update(
        task_always_eager=task_always_eager,
        task_eager_propagates=True,
        task_track_started=True,
    )

    return celery_application


celery_app = create_celery_app()
