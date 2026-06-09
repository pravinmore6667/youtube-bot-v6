import logging
import re

logger = logging.getLogger(__name__)

class ContentSafetyEngine:
    def __init__(self):
        logger.info("Initializing ContentSafetyEngine...")
        # Compile lists of restricted terms or patterns
        self.banned_words = [r'\bspam\b', r'\bscam\b', r'\bclickbait\b']

    def analyze_content(self, script, visuals_metadata):
        """
        Detects copyright risks, policy violations, unsafe content,
        and demonetization risks.
        """
        logger.info("Analyzing content for safety and policy compliance...")

        script_safe = self._check_script_safety(script)
        visuals_safe = self._check_visuals_safety(visuals_metadata)
        reused_risk = self._check_reused_content_risk(script, visuals_metadata)

        overall_safe = script_safe and visuals_safe and not reused_risk

        return {
            'is_safe': overall_safe,
            'script_safety': script_safe,
            'visuals_safety': visuals_safe,
            'reused_content_risk': reused_risk,
            'action': 'approved' if overall_safe else 'flagged_for_review'
        }

    def _check_script_safety(self, script):
        for pattern in self.banned_words:
            if re.search(pattern, script, re.IGNORECASE):
                logger.warning(f"Safety risk detected in script: matched {pattern}")
                return False
        return True

    def _check_visuals_safety(self, metadata):
        # Mocking check for NSFW tags or copyright claims in metadata
        if "nsfw" in metadata.get("tags", []):
            return False
        return True

    def _check_reused_content_risk(self, script, metadata):
        # Mocking logic that checks if content overlaps heavily with database
        return metadata.get("overlap_score", 0.0) > 0.8

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    engine = ContentSafetyEngine()
    result = engine.analyze_content("This is a safe video script.", {"tags": ["education"], "overlap_score": 0.1})
    print(result)
