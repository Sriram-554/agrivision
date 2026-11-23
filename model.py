"""Demo prediction service prepared for later Scikit-learn integration.

No trained model or accuracy claim is made here.
"""


def predict_yield_demo(crop_type, area, soil_moisture, temperature, humidity):
    crop_factors = {
        "Rice": 4.8,
        "Wheat": 3.6,
        "Maize": 5.4,
        "Cotton": 2.2,
        "Sugarcane": 70.0,
        "Tomato": 35.0,
        "Potato": 22.0,
        "Soybean": 2.4,
    }
    factor = crop_factors.get(crop_type, 4.0)
    moisture_score = max(0.72, min(1.12, 1 - abs(soil_moisture - 55) / 120))
    temp_score = max(0.78, min(1.08, 1 - abs(temperature - 25) / 100))
    humidity_score = max(0.82, min(1.05, 1 - abs(humidity - 65) / 180))
    return round(factor * float(area) * moisture_score * temp_score * humidity_score, 2)
