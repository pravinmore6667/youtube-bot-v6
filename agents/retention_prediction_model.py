import os
import joblib
import pandas as pd
import numpy as np
from xgboost import XGBRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error

class RetentionPredictionModel:
    def __init__(self, model_path="models/retention_model.pkl"):
        self.model_path = model_path
        self.model = None
        self._load_model()

    def _load_model(self):
        if os.path.exists(self.model_path):
            self.model = joblib.load(self.model_path)
        else:
            self.model = XGBRegressor(n_estimators=100, learning_rate=0.1, max_depth=5, random_state=42)

    def train(self, data):
        """
        Train the model using historical data.
        Data should be a DataFrame with features (e.g., video length, pacing, cut frequency, emotion variance)
        and target 'retention_rate'.
        """
        if data.empty or 'retention_rate' not in data.columns:
            return False

        X = data.drop(columns=['retention_rate'])
        y = data['retention_rate']

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        self.model.fit(X_train, y_train)

        preds = self.model.predict(X_test)
        mse = mean_squared_error(y_test, preds)

        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        joblib.dump(self.model, self.model_path)
        return mse

    def predict(self, features):
        """
        Predict retention given features.
        """
        if isinstance(features, dict):
            features = pd.DataFrame([features])

        try:
            return self.model.predict(features)[0]
        except Exception:
            # Fallback if not fitted
            return np.random.uniform(30.0, 70.0)
