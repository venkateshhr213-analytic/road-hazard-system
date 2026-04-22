import pandas as pd
from sklearn.ensemble import RandomForestClassifier

# Sample dataset
data = {
    'road_condition':[2,4,1,3,2,4,1,3],
    'traffic':[3,2,4,1,3,2,4,1],
    'weather':[1,0,2,0,1,0,2,0],
    'accident_history':[1,0,1,0,1,0,1,0],
    'hazard':[1,0,1,0,1,0,1,0]
}

df = pd.DataFrame(data)

X = df[['road_condition','traffic','weather','accident_history']]
y = df['hazard']

# Train model
model = RandomForestClassifier(n_estimators=100)
model.fit(X, y)

# Prediction function
def predict_hazard(road_condition, traffic, weather, accident_history):
    data = [[road_condition, traffic, weather, accident_history]]
    return model.predict(data)[0]