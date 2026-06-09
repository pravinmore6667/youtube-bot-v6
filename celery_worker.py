import os
from celery import Celery
from utils.logger import get_logger

log = get_logger("CeleryWorker")

# Initialize Celery app
redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
celery_app = Celery('youtube_ai_bot', broker=redis_url, backend=redis_url)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    worker_concurrency=int(os.environ.get('CELERY_CONCURRENCY', '2')),
    worker_prefetch_multiplier=1,
)

@celery_app.task(bind=True, name="run_pipeline")
def run_pipeline_task(self, topic: str = None):
    """
    Celery task to run the video generation pipeline autonomously.
    """
    log.info(f"Starting Celery Pipeline Task for topic: {topic}")
    from pipeline import run
    try:
        result = run(manual_topic=topic)
        log.success(f"Celery Pipeline Task completed successfully for job: {result.get('id')}")
        return result
    except Exception as e:
        log.error(f"Celery Pipeline Task failed: {e}")
        raise

@celery_app.task(bind=True, name="analytics_learning_loop")
def analytics_learning_loop_task(self):
    """
    Celery task to run the self-learning feedback loop.
    """
    log.info("Starting Celery Analytics Learning Loop Task...")
    import asyncio
    from agents.analytics_agent import analyse_and_learn, collect_all_analytics

    try:
        collect_all_analytics()
        result = asyncio.run(analyse_and_learn())
        log.success("Celery Analytics Learning Loop completed.")
        return result
    except Exception as e:
        log.error(f"Celery Analytics Learning Loop failed: {e}")
        raise
