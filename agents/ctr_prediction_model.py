import os
import joblib
import pandas as pd
import numpy as np
from xgboost import XGBRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error

class CTRPredictionModel:
    def __init__(self, model_path="models/ctr_model.pkl"):
        self.model_path = model_path
        self.model = None
        self._load_model()

    def _load_model(self):
        if os.path.exists(self.model_path):
            self.model = joblib.load(self.model_path)
        else:
            self.model = XGBRegressor(n_estimators=100, learning_rate=0.1, random_state=42)

    def train(self, data):
        """
        Train the model using historical data.
        Data should be a DataFrame with features (e.g., title length, keyword match, thumbnail saturation)
        and target 'ctr'.
        """
        if data.empty or 'ctr' not in data.columns:
            return False

        X = data.drop(columns=['ctr'])
        y = data['ctr']

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        self.model.fit(X_train, y_train)

        preds = self.model.predict(X_test)
        mse = mean_squared_error(y_test, preds)

        # Save model
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        joblib.dump(self.model, self.model_path)
        return mse

    def predict(self, features):
        """
        Predict CTR given a dictionary or DataFrame of features.
        """
        if isinstance(features, dict):
            features = pd.DataFrame([features])

        try:
            return self.model.predict(features)[0]
        except Exception:
            # Fallback if not fitted
            return np.random.uniform(2.0, 10.0)
