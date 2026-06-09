import os
import joblib
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error

class ReplayProbabilityModel:
    def __init__(self, model_path="models/replay_model.pkl"):
        self.model_path = model_path
        self.model = None
        self._load_model()

    def _load_model(self):
        if os.path.exists(self.model_path):
            self.model = joblib.load(self.model_path)
        else:
            self.model = RandomForestRegressor(n_estimators=100, random_state=42)

    def train(self, data):
        """
        Train the model using historical data.
        Data should have features (e.g., segment_density, info_density, visual_complexity)
        and target 'replay_probability'.
        """
        if data.empty or 'replay_probability' not in data.columns:
            return False

        X = data.drop(columns=['replay_probability'])
        y = data['replay_probability']

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        self.model.fit(X_train, y_train)

        preds = self.model.predict(X_test)
        mae = mean_absolute_error(y_test, preds)

        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        joblib.dump(self.model, self.model_path)
        return mae

    def predict(self, features):
        """
        Predict replay probability score given features.
        """
        if isinstance(features, dict):
            features = pd.DataFrame([features])

        try:
            return self.model.predict(features)[0]
        except Exception:
            # Fallback if not fitted
            return np.random.uniform(0.1, 0.5)
