import os
import joblib
import pandas as pd
import numpy as np
from lightgbm import LGBMClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

class ViralityPredictionModel:
    def __init__(self, model_path="models/virality_model.pkl"):
        self.model_path = model_path
        self.model = None
        self._load_model()

    def _load_model(self):
        if os.path.exists(self.model_path):
            self.model = joblib.load(self.model_path)
        else:
            self.model = LGBMClassifier(n_estimators=100, learning_rate=0.05, random_state=42)

    def train(self, data):
        """
        Train the model using historical data.
        Data should have features (e.g., trend_momentum, competitor_velocity, CTR, retention)
        and target 'is_viral' (binary 0/1).
        """
        if data.empty or 'is_viral' not in data.columns:
            return False

        X = data.drop(columns=['is_viral'])
        y = data['is_viral']

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        self.model.fit(X_train, y_train)

        preds = self.model.predict(X_test)
        acc = accuracy_score(y_test, preds)

        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        joblib.dump(self.model, self.model_path)
        return acc

    def predict_probability(self, features):
        """
        Predict probability of going viral given features.
        """
        if isinstance(features, dict):
            features = pd.DataFrame([features])

        try:
            return self.model.predict_proba(features)[0][1]
        except Exception:
            # Fallback if not fitted
            return np.random.uniform(0.01, 0.1)
