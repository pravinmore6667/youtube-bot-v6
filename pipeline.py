import os, uuid, traceback
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import config, load_live_config
from database import db
from utils.db_logger import get_logger, set_job, clear_job
from agents.holistic_agent   import (init_job, agent_start, agent_done,
                                      job_complete, save_brainstorm_result)
from agents.strategy_agent   import pick_todays_topic
from agents.decision_agent import make_autonomous_decisions
from agents.viral_intelligence_agent import analyze_viral_potential
from agents.retention_agent import optimize_retention
from agents.humanizer_agent import humanize_script
from agents.algorithm_agent import optimize_for_algorithm
from agents.thumbnail_intelligence_agent import generate_intelligent_thumbnail
from agents.channel_memory_agent import get_channel_memory, save_channel_memory
from agents.shorts_agent import optimize_for_shorts
from agents.unified_agent    import generate as unified_generate
from agents.voice_agent      import generate_voice
from agents.video_agent      import build_video
from agents.thumbnail_agent  import generate_thumbnail
from agents.caption_agent    import generate_srt, burn_captions
from agents.upload_agent     import upload_video
from utils.yt_verify         import verify_upload
from utils.checkpoint        import save_checkpoint, load_checkpoint, clear_checkpoints

log = get_logger("Pipeline")

def _step(job_id: str, name: str, fn, *args, **kwargs):
    """Wrapper to track step start/finish and agent activity."""
    db.step_start(job_id, name)
    agent_start(job_id, name)
    try:
        result = fn(*args, **kwargs)
        # For simple string outputs (paths, titles)
        out = str(result)[:500] if isinstance(result, str) else "Success"
        db.step_done(job_id, name, output=out)
        agent_done(job_id, name, summary=out)
        return result
    except Exception as e:
        db.step_done(job_id, name, error=str(e)[:500])
        agent_done(job_id, name, summary=f"Error: {e}")
        log.error(f"{name} FAILED: {e}")
        raise

def run(manual_topic: str = None) -> dict:
    load_live_config()
    job_id = uuid.uuid4().hex[:10]
    now    = datetime.utcnow().isoformat()

    job = {"id": job_id, "started_at": now, "status": "running",
           "niche": config.CHANNEL_NICHE, "language": config.CHANNEL_LANGUAGE,
           "metadata": {}}
    db.init_db()
    db.save_job(job)
    set_job(job_id)
    init_job(job_id)

    log.info("━" * 56)
    log.info(f"  🤖 PIPELINE START  [{job_id}]")
    log.info(f"  Niche: {config.CHANNEL_NICHE} | Lang: {config.CHANNEL_LANGUAGE}")
    log.info("━" * 56)

    try:
        # ── Checkpoints & Resuming ─────────────────────────────
        import asyncio
        channel_memory = asyncio.run(get_channel_memory(config.CHANNEL_NAME))
        job["channel_memory"] = channel_memory
        if manual_topic:
            decision_topic = asyncio.run(make_autonomous_decisions(manual_topic))
            if decision_topic.get("title"):
                manual_topic = decision_topic["title"]
        else:
            decision_topic = asyncio.run(make_autonomous_decisions(config.CHANNEL_NICHE))

        cp_topic = load_checkpoint("topic")
        if cp_topic and not manual_topic:
            manual_topic = cp_topic.get("title", cp_topic.get("topic"))

        asyncio.run(analyze_viral_potential(manual_topic or config.CHANNEL_NICHE, ""))

        unified = load_checkpoint("unified")

        cp_audio = load_checkpoint("voiceover")
        audio_path = cp_audio.get("audio_path") if cp_audio else None

        cp_video = load_checkpoint("video_render")
        video_path = cp_video.get("video_path") if cp_video else None

        cp_thumb = load_checkpoint("thumbnail")
        thumb_path = cp_thumb.get("thumb_path") if cp_thumb else None

        cp_srt = load_checkpoint("captions")
        srt_path = cp_srt.get("srt_path") if cp_srt else None

        # ── 1. Strategy ───────────────────────────────────────
        if not cp_topic:
            if manual_topic:
                from agents.niche_profiles import get_profile
                p     = get_profile(config.CHANNEL_NICHE)
                topic = {
                    "title":             manual_topic,
                    "angle":             "Deep-dive explainer",
                    "format":            p["video_formats"][0],
                    "keywords":          p["keywords_seed"][:5],
                    "hook":              f"What you're about to learn about {manual_topic} will surprise you.",
                    "reason":            "Manual",
                    "thumbnail_concept": manual_topic,
                    "target_emotion":    "curiosity",
                }
                db.step_start(job_id, "StrategyAgent")
                db.step_done(job_id, "StrategyAgent", output=f"Manual: {manual_topic}")
                agent_start(job_id, "StrategyAgent")
                agent_done(job_id, "StrategyAgent", summary=manual_topic)
            else:
                import asyncio
                def _run_pick_topic(*args, **kwargs):
                    return asyncio.run(pick_todays_topic(*args, **kwargs))
                topic = _step(job_id, "StrategyAgent", _run_pick_topic, config.CHANNEL_NICHE)
            save_checkpoint("topic", topic)
        else:
            topic = cp_topic

        job["topic"] = topic["title"]
        db.save_job(job)

        # ── Duplicate Prevention ──────────────────────────────
        from database.db import get_recent_jobs
        topic_title = topic["title"]
        past_jobs = get_recent_jobs(100)
        for pj in past_jobs:
            if pj.get("status") == "success" and pj.get("id") != job_id and str(topic_title).lower() in str(pj.get("topic", "")).lower():
                log.warning(f"Duplicate content detected for topic: {topic_title}. Aborting.")
                raise ValueError("Duplicate video topic detected.")

        # ── 2. UNIFIED AGENT — 1 call = script + SEO + thumbnail meta ──
        if not unified:
            log.info("🤖 UnifiedAgent: generating script + SEO in ONE call...")
            # unified_generate is now an async function
            import asyncio
            def _run_unified_generate(*args, **kwargs):
                return asyncio.run(unified_generate(*args, **kwargs))

            unified = _step(job_id, "UnifiedAgent", _run_unified_generate, topic, job_id)
            unified["optimized_narration"] = asyncio.run(humanize_script(unified.get("full_narration", "")))
            unified["optimized_narration"] = asyncio.run(optimize_retention(unified.get("optimized_narration", "")))
            if str(topic.get("format", "")).lower() == "shorts":
                unified["optimized_narration"] = asyncio.run(optimize_for_shorts(unified.get("optimized_narration", ""), topic))
            save_checkpoint("unified", unified)

        script = {
            "title":                  unified.get("title", topic["title"]),
            "format":                 unified.get("format", "explainer"),
            "language":               unified.get("language", config.CHANNEL_LANGUAGE),
            "hook":                   unified.get("hook", ""),
            "sections":               unified.get("sections", []),
            "outro":                  unified.get("outro", ""),
            "full_narration":         unified.get("optimized_narration") or unified.get("full_narration", ""),
            "word_count":             unified.get("word_count", 0),
            "estimated_duration_min": unified.get("estimated_duration_min", 6),
            "_unified_result":        unified,
        }
        seo = {
            "title":            unified.get("title", topic["title"]),
            "title_variants":   unified.get("title_variants", []),
            "description":      unified.get("description", ""),
            "tags":             unified.get("tags", []),
            "hashtags":         unified.get("hashtags", []),
            "category_id":      unified.get("category_id", "28"),
            "default_language": unified.get("default_language", "en"),
            "chapters":         unified.get("chapters", ["00:00 - Intro"]),
            "seo_score":        unified.get("seo_score", "7"),
            "primary_keyword":  unified.get("primary_keyword", ""),
        }
        if unified.get("title"):
            topic["title"] = unified["title"]
            job["topic"]   = unified["title"]
            db.save_job(job)

        log.success(f"Script: {script['word_count']} words, ~{script['estimated_duration_min']} min")

        brainstorm_compat = {
            "final_title":      unified.get("title", topic["title"]),
            "unique_angle":     unified.get("unique_angle", ""),
            "seo_keywords":     unified.get("seo_keywords", []),
            "thumbnail_concept":unified.get("thumbnail_concept", ""),
            "target_emotion":   unified.get("target_emotion", "curiosity"),
            "_unified_result":  unified,
            "agent_contributions": {"UnifiedAgent": {"note": "Single-call unified generation"}},
        }
        save_brainstorm_result(brainstorm_compat)
        db.save_brainstorm(job_id, topic["title"],
                           brainstorm_compat.get("agent_contributions", {}),
                           brainstorm_compat.get("unique_angle", ""))

        # ── 3. Voice ──────────────────────────────────────────
        if not audio_path:
            audio_path = _step(job_id, "VoiceAgent", generate_voice, script["full_narration"], job_id)
            save_checkpoint("voiceover", {"audio_path": audio_path})

        # ── 4. PARALLEL: Video + Captions + Thumbnail ─────────
        log.info("⚡ Parallel: Video | Captions | Thumbnail")

        import time
        import psutil
        from agents.editing_engine import AIEditingEngine

        def _do_video():
            if video_path: return video_path
            start_render = time.time()

            # Apply dynamic pacing via AIEditingEngine using actual audio path
            engine = AIEditingEngine(script)
            asyncio.run(engine.analyze_pacing(audio_path))
            script["_pacing_plan"] = engine.pacing_plan

            v = _step(job_id, "VideoAgent", build_video, audio_path, script, job_id)
            job["render_duration"] = time.time() - start_render
            save_checkpoint("video_render", {"video_path": v})
            return v

        def _do_captions():
            if srt_path: return srt_path
            c = _step(job_id, "CaptionAgent", generate_srt, audio_path, job_id)
            save_checkpoint("captions", {"srt_path": c})
            return c

        def _do_thumb():
            if thumb_path: return thumb_path
            t = _step(job_id, "ThumbnailAgent", lambda t_arg, j_arg, b_arg: asyncio.run(generate_intelligent_thumbnail(t_arg)), topic, job_id, brainstorm_compat)
            save_checkpoint("thumbnail", {"thumb_path": t})
            return t

        with ThreadPoolExecutor(max_workers=config.MAX_WORKERS) as ex:
            fmap = {}
            if not video_path: fmap[ex.submit(_do_video)] = "video"
            if not srt_path:   fmap[ex.submit(_do_captions)] = "captions"
            if not thumb_path: fmap[ex.submit(_do_thumb)] = "thumbnail"

            for future in as_completed(fmap):
                name = fmap[future]
                try:
                    r = future.result()
                    if   name == "video":     video_path = r
                    elif name == "captions":  srt_path   = r
                    elif name == "thumbnail": thumb_path = r
                except Exception as e:
                    log.error(f"{name} failed: {e}")
                    raise e

        # Burn captions into video
        if srt_path and video_path:
            video_path = _step(job_id, "CaptionAgent", burn_captions, video_path, srt_path)

        upload_data = {
            "title": seo["title"], "description": seo["description"],
            "tags": seo["tags"], "category_id": seo["category_id"],
            "niche": config.CHANNEL_NICHE, "language": config.CHANNEL_LANGUAGE,
            "target_audience": config.TARGET_AUDIENCE, "hook_style": topic.get("hook",""),
            "word_count": script["word_count"], "estimated_duration": script["estimated_duration_min"],
            "keywords": topic.get("keywords",[]), "job_id": job_id
        }

        upload_data = asyncio.run(optimize_for_algorithm(upload_data))

        # ── 6. Upload ─────────────────────────────────────────
        start_upload = time.time()
        upload_result = _step(job_id, "UploadAgent", upload_video, video_path, thumb_path, upload_data)
        job["upload_duration"] = time.time() - start_upload

        if upload_result and "video_id" in upload_result:
            upload_id = upload_result["video_id"]
            verify = verify_upload(upload_id)
        else:
            upload_id = None
            verify = {"verified": False, "error": "Upload failed"}
            upload_result = {"url": "", "video_id": ""}


        if verify.get("verified"):
            db.step_done(job_id, "VerifyUpload", output=f"LIVE: {verify['url']}")
            log.success(f"Video LIVE: {verify['url']}")
            db.save_video({
                "job_id":        job_id,
                "video_id":      verify["video_id"],
                "title":         verify["title"],
                "url":           verify["url"],
                "studio_url":    verify.get("studio_url", ""),
                "thumbnail_url": verify.get("thumbnail_url", ""),
                "channel":       verify.get("channel", ""),
                "published_at":  verify.get("published_at", ""),
                "duration":      verify.get("duration", ""),
                "views":         verify.get("views", 0),
                "likes":         verify.get("likes", 0),
                "verified":      True,
                "niche":         config.CHANNEL_NICHE,
                "language":      config.CHANNEL_LANGUAGE,
            })
        else:
            err = verify.get("error", "unknown")
            db.step_done(job_id, "VerifyUpload", error=err)
            log.warning(f"Verification pending: {err}")
            db.save_video({
                "job_id":    job_id,
                "video_id":  upload_result["video_id"],
                "title":     seo["title"],
                "url":       upload_result["url"],
                "studio_url": f"https://studio.youtube.com/video/{upload_result['video_id']}/edit",
                "verified":  False,
                "niche":     config.CHANNEL_NICHE,
                "language":  config.CHANNEL_LANGUAGE,
            })

        # ── Done ──────────────────────────────────────────────
        clear_checkpoints()
        job.update({
            "status":      "success",
            "finished_at": datetime.utcnow().isoformat(),
            "video_url":   upload_result["url"],
            "video_id":    upload_result["video_id"],
            "metadata": {
                "title":    seo["title"],
                "words":    script["word_count"],
                "duration": script["estimated_duration_min"],
                "format":   script.get("format", ""),
                "language": config.CHANNEL_LANGUAGE,
                "niche":    config.CHANNEL_NICHE,
                "verified": verify.get("verified", False),
            },
        })
        db.save_job(job)
        db.save_content({
            "job_id":    job_id, "title": seo["title"],
            "niche":     config.CHANNEL_NICHE,
            "language":  config.CHANNEL_LANGUAGE,
            "keywords":  topic.get("keywords", []),
            "video_url": upload_result["url"]
        })
        asyncio.run(save_channel_memory({
            "channel_id": config.CHANNEL_NAME,
            "last_title": seo["title"],
            "last_upload_time": now,
            "niche": config.CHANNEL_NICHE
        }))

        job_complete(job_id)
        clear_job()

        # End of job summary
        mem_mb = psutil.Process().memory_info().rss / (1024 * 1024)
        log.info("━" * 56)
        log.info(f"  🏁 END OF JOB SUMMARY [{job_id}]")
        log.info(f"  Topic: {seo['title']}")
        log.info(f"  Script words: {script['word_count']}")
        log.info(f"  Video duration: ~{script['estimated_duration_min']} mins")
        log.info(f"  Render time: {job.get('render_duration', 0):.1f}s")
        log.info(f"  Upload time: {job.get('upload_duration', 0):.1f}s")
        log.info(f"  Memory usage: {mem_mb:.1f} MB")
        log.info(f"  Thumbnail: {thumb_path}")
        log.info(f"  Published URL: {upload_result['url']}")
        log.info("━" * 56)

        # Try to cleanup files
        for p in [audio_path, video_path]:
            try:
                if p and os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass

    except Exception as e:
        tb = traceback.format_exc()
        log.error(f"PIPELINE FAILED:\n{tb}")
        job.update({
            "status":      "failed",
            "error":       str(e)[:500],
            "finished_at": datetime.utcnow().isoformat(),
        })
        db.save_job(job)
        job_complete(job_id)
        clear_job()

    return job
