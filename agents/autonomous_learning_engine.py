import time
import schedule
import pandas as pd
import numpy as np
import logging
from agents.ctr_prediction_model import CTRPredictionModel
from agents.retention_prediction_model import RetentionPredictionModel
from agents.virality_prediction_model import ViralityPredictionModel
from agents.replay_probability_model import ReplayProbabilityModel
from agents.engagement_prediction_model import EngagementPredictionModel

logger = logging.getLogger(__name__)

class AutonomousLearningEngine:
    def __init__(self):
        self.ctr_model = CTRPredictionModel()
        self.retention_model = RetentionPredictionModel()
        self.virality_model = ViralityPredictionModel()
        self.replay_model = ReplayProbabilityModel()
        self.engagement_model = EngagementPredictionModel()

    def _create_fallback_data(self, model_type):
        """Creates fallback datasets if the database is empty or missing."""
        num_samples = 20 # Minimal sample to initialize weights
        if model_type == 'ctr':
            return pd.DataFrame({'title_length': np.random.randint(10, 80, num_samples), 'thumbnail_saturation': np.random.uniform(0.5, 1.5, num_samples), 'keyword_match': np.random.uniform(0.1, 1.0, num_samples), 'ctr': np.random.uniform(1.0, 15.0, num_samples)})
        elif model_type == 'retention':
            return pd.DataFrame({'video_length': np.random.randint(180, 1200, num_samples), 'cut_frequency': np.random.uniform(0.1, 2.0, num_samples), 'emotion_variance': np.random.uniform(0.0, 1.0, num_samples), 'retention_rate': np.random.uniform(20.0, 80.0, num_samples)})
        elif model_type == 'virality':
            return pd.DataFrame({'trend_momentum': np.random.uniform(0.0, 1.0, num_samples), 'competitor_velocity': np.random.uniform(0.0, 1.0, num_samples), 'is_viral': np.random.randint(0, 2, num_samples)})
        elif model_type == 'replay':
            return pd.DataFrame({'segment_density': np.random.uniform(0.0, 1.0, num_samples), 'info_density': np.random.uniform(0.0, 1.0, num_samples), 'replay_probability': np.random.uniform(0.0, 1.0, num_samples)})
        elif model_type == 'engagement':
            return pd.DataFrame({'call_to_action_count': np.random.randint(0, 5, num_samples), 'controversial_score': np.random.uniform(0.0, 1.0, num_samples), 'engagement_rate': np.random.uniform(0.5, 10.0, num_samples)})

    def ingest_analytics(self):
        """
        Ingests real analytics data from SQLite/PostgreSQL database via Pandas.
        Falls back to bootstrapping logic if no real history exists yet.
        """
        logger.info("Ingesting analytics data from database...")
        try:
            import sqlite3
            # Try to connect to real analytics database
            db_path = 'database/analytics.db'
            conn = sqlite3.connect(db_path)

            # Read real tables if they exist
            tables = pd.read_sql_query("SELECT name FROM sqlite_master WHERE type='table';", conn)

            if 'ctr_history' in tables.values:
                self.ctr_data = pd.read_sql_query("SELECT title_length, thumbnail_saturation, keyword_match, ctr FROM ctr_history", conn)
            else:
                self.ctr_data = self._create_fallback_data('ctr')

            if 'retention_history' in tables.values:
                self.retention_data = pd.read_sql_query("SELECT video_length, cut_frequency, emotion_variance, retention_rate FROM retention_history", conn)
            else:
                self.retention_data = self._create_fallback_data('retention')

            if 'virality_history' in tables.values:
                self.virality_data = pd.read_sql_query("SELECT trend_momentum, competitor_velocity, is_viral FROM virality_history", conn)
            else:
                self.virality_data = self._create_fallback_data('virality')

            if 'replay_history' in tables.values:
                self.replay_data = pd.read_sql_query("SELECT segment_density, info_density, replay_probability FROM replay_history", conn)
            else:
                self.replay_data = self._create_fallback_data('replay')

            if 'engagement_history' in tables.values:
                self.engagement_data = pd.read_sql_query("SELECT call_to_action_count, controversial_score, engagement_rate FROM engagement_history", conn)
            else:
                self.engagement_data = self._create_fallback_data('engagement')

            conn.close()
        except Exception as e:
            logger.warning(f"Database ingestion failed (using fallback init data): {e}")
            self.ctr_data = self._create_fallback_data('ctr')
            self.retention_data = self._create_fallback_data('retention')
            self.virality_data = self._create_fallback_data('virality')
            self.replay_data = self._create_fallback_data('replay')
            self.engagement_data = self._create_fallback_data('engagement')

        logger.info("Analytics data ingested.")

    def retrain_models(self):
        """
        Retrain all models using the ingested analytics data.
        """
        logger.info("Retraining models...")
        if hasattr(self, 'ctr_data'):
            ctr_error = self.ctr_model.train(self.ctr_data)
            logger.info(f"CTR Model retrained. MSE: {ctr_error}")

        if hasattr(self, 'retention_data'):
            ret_error = self.retention_model.train(self.retention_data)
            logger.info(f"Retention Model retrained. MSE: {ret_error}")

        if hasattr(self, 'virality_data'):
            vir_acc = self.virality_model.train(self.virality_data)
            logger.info(f"Virality Model retrained. Accuracy: {vir_acc}")

        if hasattr(self, 'replay_data'):
            rep_error = self.replay_model.train(self.replay_data)
            logger.info(f"Replay Model retrained. MAE: {rep_error}")

        if hasattr(self, 'engagement_data'):
            eng_error = self.engagement_model.train(self.engagement_data)
            logger.info(f"Engagement Model retrained. MSE: {eng_error}")
        logger.info("All models retrained.")

    def run_learning_cycle(self):
        """
        Executes a single cycle of learning: ingestion followed by retraining.
        """
        logger.info("Starting autonomous learning cycle...")
        self.ingest_analytics()
        self.retrain_models()
        logger.info("Autonomous learning cycle completed.")

    def start_scheduler(self):
        """
        Start scheduling continuous learning loops.
        """
        schedule.every(1).days.do(self.run_learning_cycle)
        logger.info("Autonomous learning scheduler started.")
        while True:
            schedule.run_pending()
            time.sleep(60)

if __name__ == "__main__":
    import numpy as np
    logging.basicConfig(level=logging.INFO)
    engine = AutonomousLearningEngine()
    engine.run_learning_cycle()
