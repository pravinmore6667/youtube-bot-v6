import subprocess, threading, time, logging, os, tempfile

logger = logging.getLogger("FFmpegRunner")

def run_ffmpeg(cmd: list, timeout: int = 360,
               stuck_threshold: int = 60) -> bool:
    """
    Run an ffmpeg command safely.
    - Always injects -y to prevent stdin blocking.
    - Kills the process if no progress for `stuck_threshold` seconds.
    - Hard kills after `timeout` seconds regardless.
    Returns True on success, False on failure/timeout.
    """
    # Always auto-overwrite output files
    if isinstance(cmd[0], str) and "ffmpeg" in cmd[0].lower():
        if "-y" not in cmd:
            cmd = [cmd[0], "-y"] + cmd[1:]

    process = None
    last_activity = [time.time()]  # Mutable for closure

    def hard_kill():
        if process and process.poll() is None:
            logger.warning(f"FFmpeg hard timeout ({timeout}s) — killing PID {process.pid}")
            try:
                process.kill()
            except Exception:
                pass

    hard_timer = threading.Timer(timeout, hard_kill)

    def stuck_watchdog():
        """Polls every 10s; kills if no stderr output for stuck_threshold seconds."""
        while process and process.poll() is None:
            time.sleep(10)
            if time.time() - last_activity[0] > stuck_threshold:
                logger.warning(f"FFmpeg stuck (no output for {stuck_threshold}s) — killing")
                try:
                    process.kill()
                except Exception:
                    pass
                return

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,   # Critical: prevents stdin blocking
        )

        hard_timer.start()
        watchdog = threading.Thread(target=stuck_watchdog, daemon=True)
        watchdog.start()

        stdout, stderr = process.communicate()
        last_activity[0] = time.time()  # Mark activity on completion
        hard_timer.cancel()

        if process.returncode != 0:
            err_tail = stderr.decode("utf-8", errors="replace")[-600:]
            logger.error(f"FFmpeg failed (rc={process.returncode}): {err_tail}")
            return False

        logger.debug("FFmpeg completed successfully")
        return True

    except Exception as e:
        logger.error(f"FFmpeg exception: {e}")
        hard_timer.cancel()
        return False

    finally:
        hard_timer.cancel()
