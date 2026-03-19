from app.celery_app import celery_app
from app.services.job_service import JobService


@celery_app.task(name="jobs.run_analysis_pipeline")
def run_analysis_pipeline_task(job_id: str, auto_repair: bool) -> None:
    JobService().run_analysis_pipeline(job_id=job_id, auto_repair=auto_repair)


@celery_app.task(name="jobs.run_repair_pipeline")
def run_repair_pipeline_task(job_id: str) -> None:
    JobService().trigger_repair(job_id=job_id)
