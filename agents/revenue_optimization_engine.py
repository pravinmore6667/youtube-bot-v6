import logging

logger = logging.getLogger(__name__)

class RevenueOptimizationEngine:
    def __init__(self):
        logger.info("Initializing RevenueOptimizationEngine...")

    def optimize_monetization(self, video_data):
        """
        Predicts RPM, CPM, and sponsor suitability. Adjusts content structure
        to maximize revenue safely.
        """
        logger.info(f"Optimizing revenue for video: {video_data.get('title')}")

        rpm_prediction = self._predict_rpm(video_data)
        ad_suitability = self._check_ad_suitability(video_data)
        sponsor_potential = self._score_sponsor_potential(video_data)

        return {
            'predicted_rpm': rpm_prediction,
            'ad_friendly': ad_suitability,
            'sponsor_score': sponsor_potential,
            'monetization_status': 'Optimized for high RPM' if ad_suitability else 'Demonetization risk detected'
        }

    def _predict_rpm(self, data):
        # Infer RPM based on text/title length and typical financial keywords (proxy for finance niche)
        title = data.get('title', '').lower()
        if 'finance' in title or 'money' in title or 'crypto' in title:
            return 12.50
        elif 'gaming' in title or 'game' in title:
            return 3.50
        else:
            return 6.00

    def _check_ad_suitability(self, data):
        title = data.get('title', '').lower()
        # Simple proxy check for ad suitability
        banned_words = ['kill', 'murder', 'blood', 'sex', 'nsfw', 'hack']
        for word in banned_words:
            if word in title:
                return False
        return True

    def _score_sponsor_potential(self, data):
        # Proxy: longer, more structured titles often imply more professional content
        title = data.get('title', '')
        if len(title) > 40 and not self._check_ad_suitability(data):
            return 2.0
        elif len(title) > 40:
            return 8.5
        return 5.0

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    engine = RevenueOptimizationEngine()
    print(engine.optimize_monetization({'title': 'Finance for Beginners'}))
